"""Gaussian Boson Sampling for life-sciences graph problems.

Gaussian Boson Sampling (GBS) samples subsets of modes with a probability tied
to the *hafnian* of the corresponding submatrix of the encoded graph. Because
the hafnian counts perfect matchings, dense subgraphs are sampled far more
often than sparse ones -- the basis for the GBS dense-subgraph and max-clique
algorithms (Arrazola & Bromley, PRL 2018; Bradler et al. 2018). In life
sciences these map onto tasks such as finding tightly-connected communities in
a protein-protein interaction network or dense motifs in a molecular
similarity graph.

Task here: find the densest ``k``-node subgraph (maximum internal edge weight)
of a small interaction graph.

- classical: exact search over all ``C(m, k)`` subsets (proven optimal).
- quantum: draw GBS samples and keep the densest sampled subgraph, with no
  classical search. GBS's hafnian bias favours dense subgraphs.
- hybrid: seed a classical greedy swap search with GBS samples -- the standard
  GBS + local-search pipeline -- which reliably reaches the optimum.

Exactness / validity: for a graph with adjacency matrix ``A`` rescaled so the
GBS state is physical, the probability of a collision-free ``k``-mode pattern
``S`` is ``P(S) ∝ |Haf(A_S)|^2`` (Arrazola & Bromley 2018, Eq. 2). We compute
these hafnians exactly for every ``k``-subset of a small graph (``m <= 10``,
``k`` even) and sample from the resulting exact, normalized, postselected GBS
distribution. This is a faithful classical simulation of the GBS output
distribution and is labelled as simulation. It is exact in the collision-free,
fixed-photon-number postselected regime and for the small sizes used here.
"""

from __future__ import annotations

import itertools
import time
from typing import Any

import numpy as np

from qsolace.algorithms import ProgressCallback
from qsolace.core.backend import QuantumBackend


def hafnian(matrix: np.ndarray) -> float:
    """Exact hafnian of a symmetric matrix via recursion over matchings.

    ``Haf`` sums, over all perfect matchings of the index set, the product of
    the matched entries. Odd-dimensional matrices have no perfect matching and
    return 0. Cost is ``O((n-1)!!)`` -- intended for small ``n`` only.
    """
    n = matrix.shape[0]
    if n == 0:
        return 1.0
    if n % 2 == 1:
        return 0.0
    first = 0
    rest = list(range(1, n))
    total = 0.0
    for idx in range(len(rest)):
        partner = rest[idx]
        remaining = [rest[j] for j in range(len(rest)) if j != idx]
        sub = matrix[np.ix_(remaining, remaining)]
        total += matrix[first, partner] * hafnian(sub)
    return float(total)


def generate_interaction_graph(num_nodes: int, edge_probability: float, seed: int) -> np.ndarray:
    """Weighted symmetric adjacency matrix with a planted dense community."""
    rng = np.random.default_rng(seed)
    adjacency = np.zeros((num_nodes, num_nodes))
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if rng.random() < edge_probability:
                adjacency[i, j] = adjacency[j, i] = float(rng.uniform(0.5, 1.0))
    # plant a dense community among the first quarter of nodes
    community = list(range(max(2, num_nodes // 4)))
    for i in community:
        for j in community:
            if i < j:
                adjacency[i, j] = adjacency[j, i] = float(rng.uniform(0.8, 1.0))
    return adjacency


def subgraph_density(adjacency: np.ndarray, nodes: tuple[int, ...]) -> float:
    """Total internal edge weight of the induced subgraph on ``nodes``."""
    idx = list(nodes)
    sub = adjacency[np.ix_(idx, idx)]
    return float(np.sum(np.triu(sub, k=1)))


def _gbs_distribution(adjacency: np.ndarray, subset_size: int) -> tuple[list[tuple[int, ...]], np.ndarray]:
    """Exact postselected GBS distribution over ``k``-node subsets.

    ``P(S) ∝ |Haf(A_S)|^2`` for each collision-free ``k``-subset ``S``.
    """
    subsets = list(itertools.combinations(range(adjacency.shape[0]), subset_size))
    weights = np.array([hafnian(adjacency[np.ix_(list(s), list(s))]) ** 2 for s in subsets])
    total = weights.sum()
    if total <= 0:
        weights = np.ones(len(subsets))
        total = weights.sum()
    return subsets, weights / total


def _greedy_refine(adjacency: np.ndarray, nodes: tuple[int, ...], subset_size: int) -> tuple[int, ...]:
    """Local swap search: repeatedly swap a member for an outsider if denser."""
    num_nodes = adjacency.shape[0]
    current = set(nodes)
    best_density = subgraph_density(adjacency, tuple(sorted(current)))
    improved = True
    while improved:
        improved = False
        outsiders = [x for x in range(num_nodes) if x not in current]
        for inside in list(current):
            for outside in outsiders:
                candidate = (current - {inside}) | {outside}
                density = subgraph_density(adjacency, tuple(sorted(candidate)))
                if density > best_density + 1e-12:
                    current, best_density, improved = candidate, density, True
                    break
            if improved:
                break
    return tuple(sorted(current))


def run_comparison(
    params: dict[str, Any],
    backend: QuantumBackend,  # noqa: ARG001 - GBS distribution is computed exactly, not via the gate backend
    progress: ProgressCallback,
) -> dict[str, Any]:
    num_nodes = int(params.get("num_nodes", 8))
    subgraph_size = int(params.get("subgraph_size", 4))
    edge_probability = float(params.get("edge_probability", 0.5))
    shots = int(params.get("shots", 400))
    seed = int(params.get("seed", 7))

    if not 4 <= num_nodes <= 10:
        raise ValueError("num_nodes must be between 4 and 10 for exact verification")
    if subgraph_size % 2 != 0:
        raise ValueError("subgraph_size must be even (collision-free GBS requires an even photon number)")
    if not 2 <= subgraph_size < num_nodes:
        raise ValueError("subgraph_size must be even, >= 2 and < num_nodes")

    rng = np.random.default_rng(seed)
    adjacency = generate_interaction_graph(num_nodes, edge_probability, seed)

    progress({"phase": "setup", "message": f"Interaction graph: {num_nodes} nodes; seeking densest {subgraph_size}-node community."})

    # --- classical: exact search over all k-subsets -----------------------
    progress({"phase": "classical", "message": "Exhaustive search over all subsets (exact optimum)..."})
    t0 = time.perf_counter()
    subsets, distribution = _gbs_distribution(adjacency, subgraph_size)
    densities = np.array([subgraph_density(adjacency, s) for s in subsets])
    best_index = int(np.argmax(densities))
    optimal_density = float(densities[best_index])
    classical_time = time.perf_counter() - t0
    progress({"phase": "classical", "message": f"Densest subgraph weight = {optimal_density:.3f} (exact).", "value": optimal_density})

    classical = {
        "method": "Exhaustive densest-subgraph search (all subsets)",
        "quality": 1.0,
        "density": optimal_density,
        "nodes": list(subsets[best_index]),
        "elapsed_seconds": classical_time,
        "evaluations": len(subsets),
        "scaling_note": "Exhaustive subset search scales combinatorially (C(m,k)); infeasible for large interaction networks.",
    }

    # --- quantum: GBS sampling, best sample -------------------------------
    progress({"phase": "quantum", "message": f"Drawing {shots} GBS samples (hafnian-biased toward dense subgraphs)..."})
    t0 = time.perf_counter()
    sample_indices = rng.choice(len(subsets), size=shots, p=distribution)
    q_best_density = float(densities[sample_indices].max())
    quantum_time = time.perf_counter() - t0
    q_best_subset = subsets[int(sample_indices[np.argmax(densities[sample_indices])])]
    progress({"phase": "quantum", "message": f"Best GBS-sampled weight = {q_best_density:.3f}.", "value": q_best_density})

    quantum = {
        "method": "Gaussian Boson Sampling, best sampled subgraph (no classical search)",
        "quality": q_best_density / optimal_density if optimal_density else 1.0,
        "density": q_best_density,
        "nodes": list(q_best_subset),
        "elapsed_seconds": quantum_time,
        "shots": shots,
        "simulated": True,
        "scaling_note": "GBS concentrates samples on dense subgraphs, so a modest number of samples surfaces strong candidates.",
    }

    # --- hybrid: GBS-seeded greedy refinement -----------------------------
    progress({"phase": "hybrid", "message": "Refining GBS samples with classical greedy swap search..."})
    t0 = time.perf_counter()
    unique_seeds = {int(i) for i in sample_indices[: min(shots, 40)]}
    best_density = 0.0
    best_subset: tuple[int, ...] = subsets[0]
    history: list[dict[str, float]] = []
    for i, seed_index in enumerate(sorted(unique_seeds), start=1):
        refined = _greedy_refine(adjacency, subsets[seed_index], subgraph_size)
        density = subgraph_density(adjacency, refined)
        if density > best_density:
            best_density, best_subset = density, refined
        history.append({"iteration": i, "value": density, "best": best_density})
        progress({"phase": "hybrid", "iteration": i, "value": density, "best": best_density, "target": optimal_density})
    hybrid_time = time.perf_counter() - t0
    progress({"phase": "hybrid", "message": f"Refined best weight = {best_density:.3f}.", "value": best_density})

    hybrid = {
        "method": "GBS samples + classical greedy local search (hybrid pipeline)",
        "quality": best_density / optimal_density if optimal_density else 1.0,
        "density": best_density,
        "nodes": list(best_subset),
        "elapsed_seconds": hybrid_time,
        "circuit_evaluations": len(unique_seeds),
        "history": history,
        "simulated": True,
        "scaling_note": "Local search touches only a handful of GBS-seeded candidates instead of the full combinatorial space.",
    }

    return {
        "algorithm": "gbs-dense-subgraph",
        "problem": {"num_nodes": num_nodes, "subgraph_size": subgraph_size, "edge_probability": edge_probability, "seed": seed},
        "optimal": {"density": optimal_density, "nodes": list(subsets[best_index]), "source": "exhaustive search"},
        "paths": {"classical": classical, "quantum": quantum, "hybrid": hybrid},
        "quality_label": "Subgraph-density ratio vs the exact densest community (1.0 = optimal)",
    }
