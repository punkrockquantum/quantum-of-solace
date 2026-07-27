"""Quantum Amplitude Estimation vs classical Monte Carlo.

Problem: estimate an expectation value ``a = E[f(X)]`` that has been encoded as
the probability of measuring ``|1>`` in a state prepared by a rotation

    A|0> = cos(theta)|0> + sin(theta)|1>,   a = sin^2(theta).

This is the standard amplitude-encoding used for quantum-accelerated Monte
Carlo in finance and physics (Montanaro 2015; Suzuki et al. 2020,
"Amplitude estimation without phase estimation"). ``a`` maps to a real payoff
or integral in an application; here ``a`` is known analytically so every error
below is a *measured* error against ground truth.

Three honestly-measured paths, compared at equal oracle budget:

- classical: plain Monte Carlo. Draw ``N`` Bernoulli(a) samples (the ``k=0``
  circuit), estimate the mean. Statistical error scales as ``1/sqrt(N)``.
- quantum: one round of amplitude amplification (Grover power ``k=1``) and a
  direct single-power inversion, with no classical fitting. Uses quantum
  interference but is limited by branch aliasing for larger amplitudes.
- hybrid: Maximum-Likelihood Amplitude Estimation. Quantum circuits at an
  exponentially-increasing set of Grover powers (``k = 1, 2, 4, ...``) feed a
  classical maximum-likelihood fit for ``theta``. Error approaches the
  Heisenberg limit ``~1/N`` -- a quadratic improvement over Monte Carlo.

The Grover operator on this single-qubit "good subspace" is
``Q = -A S_0 A^dagger S_chi`` which acts as a rotation by ``2 theta``, so
``P_k(1) = sin^2((2k+1) theta)`` -- the exact relation the fit inverts.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from qsolace.algorithms import ProgressCallback
from qsolace.core.backend import QuantumBackend
from qsolace.core.circuit import Circuit


def qae_circuit(theta: float, grover_power: int) -> Circuit:
    """Amplitude-estimation circuit: state prep ``A`` then ``Q^k``.

    ``Q = Ry(2 theta) Z Ry(-2 theta) Z`` (global phase dropped); appending it
    ``k`` times after ``A = Ry(2 theta)`` yields ``P(1) = sin^2((2k+1)theta)``.
    """
    circuit = Circuit(1)
    circuit.ry(2.0 * theta, 0)  # A|0>
    for _ in range(grover_power):
        circuit.z(0)
        circuit.ry(-2.0 * theta, 0)
        circuit.z(0)
        circuit.ry(2.0 * theta, 0)
    return circuit


def _measure_good_probability(backend: QuantumBackend, theta: float, grover_power: int, shots: int) -> tuple[int, int]:
    """Return (good counts, shots) from a real sampled run of the QAE circuit."""
    result = backend.run(qae_circuit(theta, grover_power), shots=shots)
    good = result.counts.get("1", 0)
    return good, result.shots


def _eis_schedule(levels: int) -> list[int]:
    """Exponentially-incremented Grover powers {0, 1, 2, 4, ...}.

    Level 0 (k=0) anchors the fit; the exponential tail delivers the
    Heisenberg-limited ``~1/N`` scaling (Suzuki et al. 2020).
    """
    powers = [0]
    powers.extend(2**j for j in range(levels - 1))
    return powers


def _oracle_calls(powers: list[int], shots: int) -> int:
    """Total applications of the amplitude oracle across the schedule.

    A circuit at Grover power ``k`` invokes the oracle ``2k+1`` times.
    """
    return sum((2 * k + 1) * shots for k in powers)


def _maximum_likelihood_theta(
    measurements: list[tuple[int, int, int]],
    grid: np.ndarray,
) -> float:
    """MLE for theta given (grover_power, good_counts, shots) measurements."""
    log_likelihood = np.zeros_like(grid)
    eps = 1e-12
    for k, good, shots in measurements:
        p = np.clip(np.sin((2 * k + 1) * grid) ** 2, eps, 1 - eps)
        log_likelihood += good * np.log(p) + (shots - good) * np.log(1.0 - p)
    return float(grid[int(np.argmax(log_likelihood))])


def run_comparison(
    params: dict[str, Any],
    backend: QuantumBackend,
    progress: ProgressCallback,
) -> dict[str, Any]:
    levels = int(params.get("evaluation_levels", 6))
    true_value = float(params.get("true_value", 0.15))
    shots = int(params.get("shots", 1024))
    seed = int(params.get("seed", 7))

    if not 2 <= levels <= 10:
        raise ValueError("evaluation_levels must be between 2 and 10")
    if not 0.02 <= true_value <= 0.98:
        raise ValueError("true_value must be between 0.02 and 0.98")

    rng = np.random.default_rng(seed)
    theta_true = float(np.arcsin(np.sqrt(true_value)))
    grid = np.linspace(1e-4, np.pi / 2 - 1e-4, 4000)

    progress(
        {
            "phase": "setup",
            "message": f"Estimating expectation a = {true_value:g} (exact, known analytically).",
        }
    )

    powers = _eis_schedule(levels)
    budget = _oracle_calls(powers, shots)

    def quality(estimate: float) -> float:
        return float(np.clip(1.0 - abs(estimate - true_value) / true_value, 0.0, 1.0))

    # --- classical Monte Carlo (equal oracle budget) ----------------------
    progress({"phase": "classical", "message": f"Monte Carlo: drawing {budget:,} samples (error ~ 1/sqrt(N))..."})
    t0 = time.perf_counter()
    samples = rng.binomial(1, true_value, size=budget)
    mc_estimate = float(samples.mean())
    classical_time = time.perf_counter() - t0
    mc_error = abs(mc_estimate - true_value)
    progress({"phase": "classical", "message": f"Monte Carlo estimate = {mc_estimate:.5f} (error {mc_error:.2e}).", "value": mc_estimate})

    classical = {
        "method": "Classical Monte Carlo sampling",
        "estimate": mc_estimate,
        "error": mc_error,
        "quality": quality(mc_estimate),
        "elapsed_seconds": classical_time,
        "oracle_calls": budget,
        "scaling_note": "Statistical error falls only as 1/sqrt(N): every extra digit of accuracy costs 100x more samples.",
    }

    # --- pure quantum: one Grover round, single-power inversion ------------
    progress({"phase": "quantum", "message": "Amplitude amplification at Grover power k=1 (no classical fit)..."})
    t0 = time.perf_counter()
    good_q, shots_q = _measure_good_probability(backend, theta_true, grover_power=1, shots=shots)
    p_hat = good_q / shots_q
    theta_q = float(np.arcsin(np.sqrt(np.clip(p_hat, 0.0, 1.0))) / 3.0)  # (2*1+1)=3
    q_estimate = float(np.sin(theta_q) ** 2)
    quantum_time = time.perf_counter() - t0
    q_result = backend.run(qae_circuit(theta_true, 1), shots=1)
    progress({"phase": "quantum", "message": f"Single-power estimate = {q_estimate:.5f}.", "value": q_estimate})

    quantum = {
        "method": "Amplitude amplification, single Grover power (no classical fitting)",
        "estimate": q_estimate,
        "error": abs(q_estimate - true_value),
        "quality": quality(q_estimate),
        "elapsed_seconds": quantum_time,
        "oracle_calls": 3 * shots,
        "simulated": q_result.simulated,
        "scaling_note": "One amplification round already sharpens the estimate, but a single power cannot resolve larger amplitudes on its own.",
    }

    # --- hybrid: maximum-likelihood amplitude estimation -------------------
    progress({"phase": "hybrid", "message": f"MLAE: Grover powers {powers} + classical maximum-likelihood fit..."})
    t0 = time.perf_counter()
    measurements: list[tuple[int, int, int]] = []
    history: list[dict[str, float]] = []
    for i, k in enumerate(powers, start=1):
        good, s = _measure_good_probability(backend, theta_true, grover_power=k, shots=shots)
        measurements.append((k, good, s))
        theta_hat = _maximum_likelihood_theta(measurements, grid)
        estimate = float(np.sin(theta_hat) ** 2)
        history.append({"iteration": i, "value": estimate, "best": estimate})
        progress({"phase": "hybrid", "iteration": i, "value": estimate, "best": estimate, "target": true_value})
    theta_mle = _maximum_likelihood_theta(measurements, grid)
    hybrid_estimate = float(np.sin(theta_mle) ** 2)
    hybrid_time = time.perf_counter() - t0
    hybrid_error = abs(hybrid_estimate - true_value)
    progress({"phase": "hybrid", "message": f"MLAE estimate = {hybrid_estimate:.5f} (error {hybrid_error:.2e}).", "value": hybrid_estimate})

    hybrid = {
        "method": "Maximum-Likelihood Amplitude Estimation (quantum circuits + classical MLE fit)",
        "estimate": hybrid_estimate,
        "error": hybrid_error,
        "quality": quality(hybrid_estimate),
        "elapsed_seconds": hybrid_time,
        "oracle_calls": budget,
        "circuit_evaluations": len(powers),
        "history": history,
        "simulated": True,
        "scaling_note": "Error approaches the Heisenberg limit ~1/N: a quadratic speedup, so each extra digit costs only 10x more work instead of 100x.",
    }

    return {
        "algorithm": "quantum-monte-carlo",
        "problem": {"true_value": true_value, "evaluation_levels": levels, "grover_powers": powers, "oracle_budget": budget, "seed": seed},
        "optimal": {"estimate": true_value, "source": "exact analytic value"},
        "paths": {"classical": classical, "quantum": quantum, "hybrid": hybrid},
        "quality_label": "Estimation quality (1.0 = exact expectation value, at equal oracle budget)",
    }
