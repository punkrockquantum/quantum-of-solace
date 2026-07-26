"""VQE ground-state search for the transverse-field Ising model.

Hamiltonian (open chain of n spins):

    H = -J * sum_i Z_i Z_{i+1}  -  h * sum_i X_i

Paths compared (all measured, nothing estimated):

- classical: exact dense diagonalization (numpy.linalg.eigh) - ground truth;
  memory/cost grows as 4^n.
- quantum: evaluate the ansatz energy at random, unoptimized parameters and
  keep the lowest - quantum hardware alone, no classical help.
- hybrid: COBYLA (classical, HPC-side) tunes a hardware-efficient RY+CX
  ansatz to minimize the measured energy.

Quality is reported as relative energy error against the exact ground state.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import minimize

from qsolace.algorithms import ProgressCallback
from qsolace.core.backend import QuantumBackend
from qsolace.core.circuit import Circuit


# ---------------------------------------------------------------------------
# Hamiltonian
# ---------------------------------------------------------------------------
def build_hamiltonian(num_qubits: int, coupling_j: float, field_h: float) -> np.ndarray:
    """Dense matrix of H in the computational basis.

    Index convention matches the simulator: bit q of the basis index is
    qubit q (little-endian).
    """
    dim = 2**num_qubits
    bits = (np.arange(dim)[:, None] >> np.arange(num_qubits)) & 1  # (dim, n)
    z = 1.0 - 2.0 * bits  # Z eigenvalue per qubit
    hamiltonian = np.diag(-coupling_j * np.sum(z[:, :-1] * z[:, 1:], axis=1))
    indices = np.arange(dim)
    for q in range(num_qubits):
        flipped = indices ^ (1 << q)
        hamiltonian[indices, flipped] += -field_h
    return hamiltonian


# ---------------------------------------------------------------------------
# Ansatz
# ---------------------------------------------------------------------------
def num_parameters(num_qubits: int, layers: int) -> int:
    return num_qubits * (layers + 1)


def ansatz_circuit(num_qubits: int, layers: int, theta: np.ndarray) -> Circuit:
    """Hardware-efficient ansatz: RY layer, then [CX chain + RY layer] x L."""
    c = Circuit(num_qubits)
    k = 0
    for q in range(num_qubits):
        c.ry(float(theta[k]), q)
        k += 1
    for _ in range(layers):
        for q in range(num_qubits - 1):
            c.cx(q, q + 1)
        for q in range(num_qubits):
            c.ry(float(theta[k]), q)
            k += 1
    return c


# ---------------------------------------------------------------------------
# Energy measurement
# ---------------------------------------------------------------------------
def measure_energy(
    backend: QuantumBackend,
    num_qubits: int,
    layers: int,
    theta: np.ndarray,
    coupling_j: float,
    field_h: float,
    hamiltonian: np.ndarray,
    shots: int,
) -> float:
    """<H> for the ansatz state.

    Exact via statevector when the backend supports it; otherwise estimated
    from two measured circuits (Z basis for the ZZ terms, X basis for the
    field terms) exactly as on real hardware.
    """
    circuit = ansatz_circuit(num_qubits, layers, theta)

    if hasattr(backend, "statevector"):
        psi = backend.statevector(circuit)
        return float(np.real(psi.conj() @ (hamiltonian @ psi)))

    # --- counts-based estimation (hardware path) ---
    # ZZ terms: measure in the computational basis.
    z_result = backend.run(circuit, shots=shots)
    zz_sum = 0.0
    for bitstring, count in z_result.counts.items():
        z = np.array([1.0 - 2.0 * int(b) for b in bitstring])
        zz_sum += count * float(np.sum(z[:-1] * z[1:]))
    zz_expectation = zz_sum / z_result.shots

    # X terms: rotate every qubit with H, then <X_q> = <Z_q> in the new basis.
    x_circuit = ansatz_circuit(num_qubits, layers, theta)
    for q in range(num_qubits):
        x_circuit.h(q)
    x_result = backend.run(x_circuit, shots=shots)
    x_sum = 0.0
    for bitstring, count in x_result.counts.items():
        x_sum += count * float(np.sum([1.0 - 2.0 * int(b) for b in bitstring]))
    x_expectation = x_sum / x_result.shots

    return float(-coupling_j * zz_expectation - field_h * x_expectation)


# ---------------------------------------------------------------------------
# Execution paths
# ---------------------------------------------------------------------------
def run_comparison(
    params: dict[str, Any],
    backend: QuantumBackend,
    progress: ProgressCallback,
) -> dict[str, Any]:
    num_qubits = int(params.get("num_qubits", 4))
    layers = int(params.get("layers", 2))
    coupling_j = float(params.get("coupling_j", 1.0))
    field_h = float(params.get("field_h", 1.0))
    shots = int(params.get("shots", 2048))
    max_iterations = int(params.get("max_iterations", 150))
    seed = int(params.get("seed", 7))

    if not 2 <= num_qubits <= 10:
        raise ValueError("num_qubits must be between 2 and 10 for exact classical verification")

    rng = np.random.default_rng(seed)
    hamiltonian = build_hamiltonian(num_qubits, coupling_j, field_h)
    n_params = num_parameters(num_qubits, layers)

    progress(
        {
            "phase": "setup",
            "message": f"Transverse-field Ising chain: {num_qubits} spins, J={coupling_j:g}, h={field_h:g}.",
        }
    )

    # --- classical: exact diagonalization ----------------------------------
    progress({"phase": "classical", "message": f"Exact diagonalization of the {2**num_qubits}x{2**num_qubits} Hamiltonian..."})
    t0 = time.perf_counter()
    eigenvalues = np.linalg.eigvalsh(hamiltonian)
    ground_energy = float(eigenvalues[0])
    max_energy = float(eigenvalues[-1])
    classical_time = time.perf_counter() - t0
    progress({"phase": "classical", "message": f"Exact ground energy = {ground_energy:.6f}.", "value": ground_energy})

    classical = {
        "method": "Exact dense diagonalization (LAPACK eigh)",
        "energy": ground_energy,
        "energy_error": 0.0,
        "quality": 1.0,
        "elapsed_seconds": classical_time,
        "scaling_note": "Memory and time grow as 4^n; exact diagonalization stops being feasible near n = 20-25 spins.",
    }

    energy_span = max(max_energy - ground_energy, 1e-12)

    def quality(energy: float) -> float:
        """1.0 = exact ground state, 0.0 = worst possible state."""
        return float(np.clip(1.0 - (energy - ground_energy) / energy_span, 0.0, 1.0))

    # --- quantum only: random-parameter evaluations -------------------------
    n_random = 10
    progress({"phase": "quantum", "message": f"Measuring energy at {n_random} random (unoptimized) ansatz settings..."})
    t0 = time.perf_counter()
    q_best_energy = np.inf
    for _ in range(n_random):
        theta = rng.uniform(-np.pi, np.pi, size=n_params)
        energy = measure_energy(backend, num_qubits, layers, theta, coupling_j, field_h, hamiltonian, shots)
        q_best_energy = min(q_best_energy, energy)
    quantum_time = time.perf_counter() - t0
    progress({"phase": "quantum", "message": f"Best random-parameter energy = {q_best_energy:.6f}.", "value": q_best_energy})

    quantum = {
        "method": f"Ansatz energy at {n_random} random parameter settings (no classical optimization)",
        "energy": float(q_best_energy),
        "energy_error": float(q_best_energy - ground_energy),
        "quality": quality(q_best_energy),
        "elapsed_seconds": quantum_time,
    }

    # --- hybrid: VQE loop ----------------------------------------------------
    progress({"phase": "hybrid", "message": f"Hybrid VQE: COBYLA tuning {n_params} ansatz parameters..."})
    t0 = time.perf_counter()
    evaluations = 0
    best_energy = np.inf
    history: list[dict[str, float]] = []

    def objective(theta: np.ndarray) -> float:
        nonlocal evaluations, best_energy
        energy = measure_energy(backend, num_qubits, layers, theta, coupling_j, field_h, hamiltonian, shots)
        evaluations += 1
        best_energy = min(best_energy, energy)
        history.append({"iteration": evaluations, "energy": energy, "best": best_energy})
        progress(
            {
                "phase": "hybrid",
                "iteration": evaluations,
                "value": energy,
                "best": best_energy,
                "target": ground_energy,
            }
        )
        return energy

    x0 = rng.uniform(-0.5, 0.5, size=n_params)
    minimize(objective, x0, method="COBYLA", options={"maxiter": max_iterations, "rhobeg": 0.4})
    hybrid_time = time.perf_counter() - t0
    progress(
        {
            "phase": "hybrid",
            "message": f"Hybrid VQE energy = {best_energy:.6f} after {evaluations} circuit evaluations "
            f"(exact ground energy {ground_energy:.6f}).",
            "value": best_energy,
        }
    )

    hybrid = {
        "method": "VQE: hardware-efficient ansatz + COBYLA classical optimizer",
        "energy": float(best_energy),
        "energy_error": float(best_energy - ground_energy),
        "quality": quality(best_energy),
        "elapsed_seconds": hybrid_time,
        "circuit_evaluations": evaluations,
        "history": history,
        "scaling_note": "Cost per iteration grows polynomially with problem size; the exponential state space lives on the quantum processor.",
    }

    return {
        "algorithm": "vqe-ising",
        "problem": {
            "num_qubits": num_qubits,
            "coupling_j": coupling_j,
            "field_h": field_h,
            "layers": layers,
            "seed": seed,
        },
        "optimal": {"energy": ground_energy, "source": "exact diagonalization"},
        "paths": {"classical": classical, "quantum": quantum, "hybrid": hybrid},
        "quality_label": "Energy quality (1.0 = exact ground state, 0.0 = worst possible state)",
    }
