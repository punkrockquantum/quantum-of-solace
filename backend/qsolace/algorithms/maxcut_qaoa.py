"""Max-Cut via QAOA: classical, quantum, and hybrid execution paths.

Problem: partition the nodes of a weighted graph into two groups so that the
total weight of edges crossing the partition (the "cut") is maximized.

Paths compared (all measured, nothing estimated):

- classical: exact brute force over all 2^n partitions (ground truth; cost
  grows exponentially with problem size).
- quantum: sample a QAOA circuit with random, unoptimized parameters and
  keep the best sampled cut - quantum hardware alone, no classical help.
- hybrid: a classical optimizer (COBYLA, an HPC-side task) tunes the QAOA
  circuit parameters, then the tuned circuit is sampled.

Quality is reported as the approximation ratio (achieved cut / optimal cut),
verified against the exact classical optimum.
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
# Problem instance
# ---------------------------------------------------------------------------
def generate_graph(num_nodes: int, edge_probability: float, seed: int) -> list[tuple[int, int, float]]:
    """Random Erdos-Renyi graph with weights 1.0; guaranteed connected enough
    to be interesting (every node gets at least one edge)."""
    rng = np.random.default_rng(seed)
    edges: list[tuple[int, int, float]] = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if rng.random() < edge_probability:
                edges.append((i, j, 1.0))
    # ensure no isolated nodes
    connected = {i for e in edges for i in e[:2]}
    for i in range(num_nodes):
        if i not in connected:
            j = int(rng.integers(0, num_nodes - 1))
            j = j if j < i else j + 1
            edges.append((min(i, j), max(i, j), 1.0))
    return edges


def cut_values(num_nodes: int, edges: list[tuple[int, int, float]]) -> np.ndarray:
    """Cut weight of every one of the 2^n partitions.

    Index convention matches the simulator: bit q of the index is node q.
    """
    indices = np.arange(2**num_nodes, dtype=np.int64)
    bits = (indices[:, None] >> np.arange(num_nodes)) & 1  # (2^n, n)
    total = np.zeros(2**num_nodes)
    for i, j, w in edges:
        total += w * (bits[:, i] != bits[:, j])
    return total


def cut_of_bitstring(bitstring: str, edges: list[tuple[int, int, float]]) -> float:
    return float(sum(w for i, j, w in edges if bitstring[i] != bitstring[j]))


# ---------------------------------------------------------------------------
# QAOA circuit
# ---------------------------------------------------------------------------
def qaoa_circuit(
    num_nodes: int,
    edges: list[tuple[int, int, float]],
    gammas: np.ndarray,
    betas: np.ndarray,
) -> Circuit:
    c = Circuit(num_nodes)
    for q in range(num_nodes):
        c.h(q)
    for gamma, beta in zip(gammas, betas):
        for i, j, w in edges:
            c.rzz(float(gamma * w), i, j)
        for q in range(num_nodes):
            c.rx(float(2.0 * beta), q)
    return c


def _expected_cut(
    backend: QuantumBackend,
    circuit: Circuit,
    values: np.ndarray,
    shots: int,
) -> float:
    """Expected cut of the circuit's output distribution.

    Uses exact probabilities when the backend exposes a statevector (as
    simulators do); otherwise estimates from measured counts, exactly as a
    real hardware run would.
    """
    if hasattr(backend, "probabilities"):
        probs = backend.probabilities(circuit)
        return float(probs @ values)
    result = backend.run(circuit, shots=shots)
    total = 0.0
    for bitstring, count in result.counts.items():
        index = int(bitstring[::-1], 2)
        total += count * values[index]
    return total / result.shots


# ---------------------------------------------------------------------------
# Execution paths
# ---------------------------------------------------------------------------
def run_comparison(
    params: dict[str, Any],
    backend: QuantumBackend,
    progress: ProgressCallback,
) -> dict[str, Any]:
    num_nodes = int(params.get("num_nodes", 8))
    edge_probability = float(params.get("edge_probability", 0.5))
    layers = int(params.get("layers", 2))
    shots = int(params.get("shots", 2048))
    max_iterations = int(params.get("max_iterations", 80))
    seed = int(params.get("seed", 7))

    if not 2 <= num_nodes <= 16:
        raise ValueError("num_nodes must be between 2 and 16 for exact classical verification")

    rng = np.random.default_rng(seed)
    edges = generate_graph(num_nodes, edge_probability, seed)
    values = cut_values(num_nodes, edges)

    progress({"phase": "setup", "message": f"Generated graph: {num_nodes} nodes, {len(edges)} edges."})

    # --- classical: exact brute force (ground truth) ----------------------
    progress({"phase": "classical", "message": f"Exact brute force over all {2**num_nodes:,} partitions..."})
    t0 = time.perf_counter()
    best_index = int(np.argmax(values))
    optimal_cut = float(values[best_index])
    classical_time = time.perf_counter() - t0
    optimal_bitstring = "".join(str((best_index >> q) & 1) for q in range(num_nodes))
    progress({"phase": "classical", "message": f"Optimal cut = {optimal_cut:g} (exact).", "value": optimal_cut})

    classical = {
        "method": "Exact brute force (all 2^n partitions)",
        "cut": optimal_cut,
        "approximation_ratio": 1.0,
        "elapsed_seconds": classical_time,
        "bitstring": optimal_bitstring,
        "evaluations": 2**num_nodes,
        "scaling_note": "Cost doubles with every added node (2^n); exact search stops being feasible near n = 40-50.",
    }

    # --- quantum only: unoptimized sampling --------------------------------
    progress({"phase": "quantum", "message": "Sampling QAOA circuit with random (unoptimized) parameters..."})
    t0 = time.perf_counter()
    random_gammas = rng.uniform(0, np.pi, size=layers)
    random_betas = rng.uniform(0, np.pi, size=layers)
    q_circuit = qaoa_circuit(num_nodes, edges, random_gammas, random_betas)
    q_result = backend.run(q_circuit, shots=shots)
    q_best_bitstring, q_best_cut = _best_sampled(q_result.counts, edges)
    q_expected = sum(c * cut_of_bitstring(b, edges) for b, c in q_result.counts.items()) / q_result.shots
    quantum_time = time.perf_counter() - t0
    progress({"phase": "quantum", "message": f"Best sampled cut = {q_best_cut:g}.", "value": q_best_cut})

    quantum = {
        "method": "QAOA sampling, random parameters (no classical optimization)",
        "cut": q_best_cut,
        "expected_cut": q_expected,
        "approximation_ratio": q_best_cut / optimal_cut if optimal_cut else 1.0,
        "elapsed_seconds": quantum_time,
        "bitstring": q_best_bitstring,
        "shots": shots,
        "simulated": q_result.simulated,
    }

    # --- hybrid: classical optimizer + quantum sampling --------------------
    progress({"phase": "hybrid", "message": f"Hybrid optimization: COBYLA tuning {2 * layers} circuit parameters..."})
    t0 = time.perf_counter()
    evaluations = 0
    best_expected = -np.inf
    history: list[dict[str, float]] = []

    def objective(theta: np.ndarray) -> float:
        nonlocal evaluations, best_expected
        gammas, betas = theta[:layers], theta[layers:]
        circuit = qaoa_circuit(num_nodes, edges, gammas, betas)
        expected = _expected_cut(backend, circuit, values, shots)
        evaluations += 1
        best_expected = max(best_expected, expected)
        history.append({"iteration": evaluations, "expected_cut": expected, "best": best_expected})
        progress(
            {
                "phase": "hybrid",
                "iteration": evaluations,
                "value": expected,
                "best": best_expected,
                "target": optimal_cut,
            }
        )
        return -expected

    x0 = rng.uniform(0.1, np.pi - 0.1, size=2 * layers)
    result = minimize(objective, x0, method="COBYLA", options={"maxiter": max_iterations, "rhobeg": 0.5})

    tuned_gammas, tuned_betas = result.x[:layers], result.x[layers:]
    final_circuit = qaoa_circuit(num_nodes, edges, tuned_gammas, tuned_betas)
    final_result = backend.run(final_circuit, shots=shots)
    h_best_bitstring, h_best_cut = _best_sampled(final_result.counts, edges)
    h_expected = _expected_cut(backend, final_circuit, values, shots)
    hybrid_time = time.perf_counter() - t0
    progress(
        {
            "phase": "hybrid",
            "message": f"Hybrid best sampled cut = {h_best_cut:g} after {evaluations} circuit evaluations.",
            "value": h_best_cut,
        }
    )

    hybrid = {
        "method": "QAOA + COBYLA classical optimizer (hybrid loop)",
        "cut": h_best_cut,
        "expected_cut": h_expected,
        "approximation_ratio": h_best_cut / optimal_cut if optimal_cut else 1.0,
        "expected_approximation_ratio": h_expected / optimal_cut if optimal_cut else 1.0,
        "elapsed_seconds": hybrid_time,
        "bitstring": h_best_bitstring,
        "circuit_evaluations": evaluations,
        "history": history,
        "shots": shots,
        "simulated": final_result.simulated,
        "scaling_note": "Cost per iteration grows polynomially with problem size; the exponential state space lives on the quantum processor.",
    }

    return {
        "algorithm": "maxcut-qaoa",
        "problem": {
            "num_nodes": num_nodes,
            "edges": [[i, j, w] for i, j, w in edges],
            "seed": seed,
            "layers": layers,
        },
        "optimal": {"cut": optimal_cut, "bitstring": optimal_bitstring, "source": "exact brute force"},
        "paths": {"classical": classical, "quantum": quantum, "hybrid": hybrid},
        "quality_label": "Approximation ratio (fraction of the mathematically optimal cut)",
    }


def _best_sampled(counts: dict[str, int], edges: list[tuple[int, int, float]]) -> tuple[str, float]:
    best_bitstring, best_cut = "", -1.0
    for bitstring in counts:
        cut = cut_of_bitstring(bitstring, edges)
        if cut > best_cut:
            best_bitstring, best_cut = bitstring, cut
    return best_bitstring, best_cut
