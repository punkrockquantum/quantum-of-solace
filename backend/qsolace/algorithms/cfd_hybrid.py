"""Hybrid CFD: a Variational Quantum Linear Solver for a discretized flow.

Many computational fluid dynamics (CFD) workloads reduce to solving a large
sparse linear system ``A x = b`` (e.g. a pressure-Poisson step, or an implicit
advection-diffusion update). We take the canonical 1D model problem -- the
finite-difference discretization of ``-u''(y) = s(y)`` with Dirichlet
boundaries, whose matrix is the symmetric positive-definite tridiagonal
Laplacian ``[[2,-1,...],[-1,2,-1,...],...]`` -- and solve it two ways.

- classical: exact dense solve (LAPACK via ``numpy.linalg.solve``). Ground
  truth; cost grows as ``O(N^3)`` for a dense solve, i.e. exponentially in the
  number of qubits ``n`` (``N = 2^n``).
- quantum: the variational ansatz at random parameters (no optimization).
- hybrid: a Variational Quantum Linear Solver (Bravo-Prieto et al. 2019).
  A classical optimizer (COBYLA) minimizes the global VQLS cost

      C(theta) = 1 - |<b| A |psi(theta)>|^2 / <psi(theta)| A^dagger A |psi(theta)>,

  which is zero exactly when ``A|psi> ∝ |b>``, i.e. when ``|psi(theta)>`` is the
  normalized solution ``x / ||x||``. The cost and the reported fidelity are
  computed from the exact statevector, so both are mathematically exact.

Quality is the state fidelity between the prepared state and the exact
normalized solution; the residual ``||A x_hat - b||`` is also reported.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import minimize

from qsolace.algorithms import ProgressCallback
from qsolace.core.backend import QuantumBackend
from qsolace.core.circuit import Circuit


def poisson_matrix(dim: int) -> np.ndarray:
    """1D Dirichlet Laplacian (SPD tridiagonal) of size ``dim``."""
    a = 2.0 * np.eye(dim) - np.eye(dim, k=1) - np.eye(dim, k=-1)
    return a


def source_vector(dim: int, seed: int) -> np.ndarray:
    """A smooth, normalized forcing term ``b`` for the flow problem."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0.0, 1.0, dim)
    b = np.sin(np.pi * y) + 0.3 * rng.standard_normal(dim)
    return b / np.linalg.norm(b)


def num_parameters(num_qubits: int, layers: int) -> int:
    return num_qubits * (layers + 1)


def ansatz_circuit(num_qubits: int, layers: int, theta: np.ndarray) -> Circuit:
    """Hardware-efficient real-amplitudes ansatz (RY layers + CX ladder)."""
    circuit = Circuit(num_qubits)
    k = 0
    for q in range(num_qubits):
        circuit.ry(float(theta[k]), q)
        k += 1
    for _ in range(layers):
        for q in range(num_qubits - 1):
            circuit.cx(q, q + 1)
        for q in range(num_qubits):
            circuit.ry(float(theta[k]), q)
            k += 1
    return circuit


def _prepared_state(backend: QuantumBackend, num_qubits: int, layers: int, theta: np.ndarray) -> np.ndarray:
    circuit = ansatz_circuit(num_qubits, layers, theta)
    if hasattr(backend, "statevector"):
        return backend.statevector(circuit)
    # Reconstruct amplitudes (magnitudes) from sampled counts for hardware.
    result = backend.run(circuit, shots=8192)
    probs = np.zeros(2**num_qubits)
    for bitstring, count in result.counts.items():
        probs[int(bitstring[::-1], 2)] = count / result.shots
    return np.sqrt(probs).astype(complex)


def vqls_cost(psi: np.ndarray, matrix: np.ndarray, b: np.ndarray) -> float:
    """Global VQLS cost; 0 iff ``A psi`` is parallel to ``b``."""
    a_psi = matrix @ psi
    denom = float(np.real(np.vdot(a_psi, a_psi)))
    if denom < 1e-15:
        return 1.0
    overlap = abs(np.vdot(b, a_psi)) ** 2
    return float(1.0 - overlap / denom)


def _fidelity_and_residual(psi: np.ndarray, matrix: np.ndarray, b: np.ndarray, x_exact: np.ndarray) -> tuple[float, float]:
    x_hat_dir = np.real(psi)
    norm = np.linalg.norm(x_hat_dir)
    if norm < 1e-15:
        return 0.0, float(np.linalg.norm(b))
    x_unit = x_hat_dir / norm
    x_exact_unit = x_exact / np.linalg.norm(x_exact)
    fidelity = float(abs(np.dot(x_unit, x_exact_unit)) ** 2)
    # scale the prepared direction to best match b, then measure the residual
    a_dir = matrix @ x_unit
    alpha = float(np.dot(b, a_dir) / np.dot(a_dir, a_dir))
    residual = float(np.linalg.norm(matrix @ (alpha * x_unit) - b))
    return fidelity, residual


def run_comparison(
    params: dict[str, Any],
    backend: QuantumBackend,
    progress: ProgressCallback,
) -> dict[str, Any]:
    num_qubits = int(params.get("num_qubits", 3))
    layers = int(params.get("layers", 3))
    max_iterations = int(params.get("max_iterations", 200))
    seed = int(params.get("seed", 7))

    if not 2 <= num_qubits <= 5:
        raise ValueError("num_qubits must be between 2 and 5 for exact verification")

    dim = 2**num_qubits
    matrix = poisson_matrix(dim)
    b = source_vector(dim, seed)
    rng = np.random.default_rng(seed)

    progress({"phase": "setup", "message": f"1D Poisson flow: {dim} grid points ({num_qubits} qubits)."})

    # --- classical exact solve --------------------------------------------
    progress({"phase": "classical", "message": f"Exact dense solve of the {dim}x{dim} system..."})
    t0 = time.perf_counter()
    x_exact = np.linalg.solve(matrix, b)
    classical_time = time.perf_counter() - t0
    progress({"phase": "classical", "message": "Exact solution obtained.", "value": 1.0})

    classical = {
        "method": "Exact dense linear solve (LAPACK)",
        "quality": 1.0,
        "fidelity": 1.0,
        "residual": float(np.linalg.norm(matrix @ x_exact - b)),
        "elapsed_seconds": classical_time,
        "scaling_note": "A dense solve costs O(N^3) = O(2^(3n)): the flow grid explodes with resolution.",
    }

    # --- pure quantum: random ansatz, selected by the measurable cost ------
    # Honest baseline: a quantum-only run cannot see the exact solution, so it
    # keeps the draw with the lowest VQLS cost (which IS measurable on
    # hardware) -- not the one that happens to match the hidden answer.
    progress({"phase": "quantum", "message": "Sampling the ansatz at random parameters (no optimization)..."})
    t0 = time.perf_counter()
    best_q_cost = np.inf
    best_q_fidelity, best_q_residual = 0.0, float(np.linalg.norm(b))
    for _ in range(10):
        theta = rng.uniform(-np.pi, np.pi, size=num_parameters(num_qubits, layers))
        psi = _prepared_state(backend, num_qubits, layers, theta)
        cost = vqls_cost(psi, matrix, b)
        if cost < best_q_cost:
            best_q_cost = cost
            best_q_fidelity, best_q_residual = _fidelity_and_residual(psi, matrix, b, x_exact)
    quantum_time = time.perf_counter() - t0
    progress({"phase": "quantum", "message": f"Best random-ansatz fidelity = {best_q_fidelity:.4f}.", "value": best_q_fidelity})

    quantum = {
        "method": "Variational ansatz at random parameters (no classical optimization)",
        "quality": best_q_fidelity,
        "fidelity": best_q_fidelity,
        "residual": best_q_residual,
        "elapsed_seconds": quantum_time,
        "simulated": True,
    }

    # --- hybrid VQLS ------------------------------------------------------
    # VQLS cost landscapes are non-convex, so we use a handful of random
    # restarts and keep the best -- standard practice for variational solvers.
    n_params = num_parameters(num_qubits, layers)
    n_restarts = 8
    progress({"phase": "hybrid", "message": f"VQLS: COBYLA minimizing the linear-system cost over {n_params} parameters ({n_restarts} restarts)..."})
    t0 = time.perf_counter()
    evaluations = 0
    best_cost = np.inf
    best_theta = np.zeros(n_params)
    history: list[dict[str, float]] = []

    def objective(theta: np.ndarray) -> float:
        nonlocal evaluations, best_cost, best_theta
        psi = _prepared_state(backend, num_qubits, layers, theta)
        cost = vqls_cost(psi, matrix, b)
        evaluations += 1
        if cost < best_cost:
            best_cost, best_theta = cost, theta.copy()
        fidelity, _ = _fidelity_and_residual(psi, matrix, b, x_exact)
        history.append({"iteration": evaluations, "value": fidelity, "best": 1.0 - best_cost})
        progress({"phase": "hybrid", "iteration": evaluations, "value": fidelity, "best": 1.0 - best_cost, "target": 1.0})
        return cost

    iters_per_restart = max(20, max_iterations // n_restarts)
    for restart in range(n_restarts):
        spread = 0.3 if restart == 0 else np.pi
        x0 = rng.uniform(-spread, spread, size=n_params)
        minimize(objective, x0, method="COBYLA", options={"maxiter": iters_per_restart, "rhobeg": 0.5})
        if best_cost < 1e-4:
            break
    psi_final = _prepared_state(backend, num_qubits, layers, best_theta)
    hybrid_fidelity, hybrid_residual = _fidelity_and_residual(psi_final, matrix, b, x_exact)
    hybrid_time = time.perf_counter() - t0
    progress({"phase": "hybrid", "message": f"VQLS fidelity = {hybrid_fidelity:.4f}, residual = {hybrid_residual:.2e}.", "value": hybrid_fidelity})

    hybrid = {
        "method": "Variational Quantum Linear Solver (ansatz + COBYLA)",
        "quality": hybrid_fidelity,
        "fidelity": hybrid_fidelity,
        "residual": hybrid_residual,
        "elapsed_seconds": hybrid_time,
        "circuit_evaluations": evaluations,
        "history": history,
        "simulated": True,
        "scaling_note": "The variational cost is evaluated with poly(n) quantum measurements; the 2^n-dimensional flow field lives in the quantum state.",
    }

    return {
        "algorithm": "cfd-vqls",
        "problem": {"num_qubits": num_qubits, "grid_points": dim, "layers": layers, "seed": seed},
        "optimal": {"fidelity": 1.0, "source": "exact linear solve"},
        "paths": {"classical": classical, "quantum": quantum, "hybrid": hybrid},
        "quality_label": "Solution fidelity vs the exact flow field (1.0 = exact)",
    }
