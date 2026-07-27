"""Correctness of the GBS, Quantum Monte Carlo, and CFD algorithms."""

import numpy as np
import pytest

from qsolace.algorithms import cfd_hybrid, gbs_lifesciences, quantum_monte_carlo
from qsolace.backends.local_simulator import LocalStatevectorSimulator


@pytest.fixture()
def sim() -> LocalStatevectorSimulator:
    return LocalStatevectorSimulator(seed=11)


# ---------------------------------------------------------------------------
# Quantum Monte Carlo / amplitude estimation
# ---------------------------------------------------------------------------
def test_qae_circuit_probability_relation(sim: LocalStatevectorSimulator) -> None:
    # P_k(1) must equal sin^2((2k+1) theta) exactly.
    theta = 0.4
    for k in (0, 1, 2, 3):
        probs = sim.probabilities(quantum_monte_carlo.qae_circuit(theta, k))
        expected = np.sin((2 * k + 1) * theta) ** 2
        assert probs[1] == pytest.approx(expected, abs=1e-9)


def test_qmc_hybrid_beats_classical_error(sim: LocalStatevectorSimulator) -> None:
    result = quantum_monte_carlo.run_comparison(
        {"true_value": 0.15, "evaluation_levels": 7, "shots": 2000, "seed": 3},
        sim,
        lambda event: None,
    )
    classical_error = result["paths"]["classical"]["error"]
    hybrid_error = result["paths"]["hybrid"]["error"]
    # at equal oracle budget, amplitude estimation should be at least as
    # accurate as Monte Carlo (typically far more accurate)
    assert hybrid_error <= classical_error + 1e-6
    assert result["paths"]["hybrid"]["quality"] >= 0.9
    assert result["optimal"]["estimate"] == 0.15


def test_qmc_oracle_budget_matches_schedule() -> None:
    powers = quantum_monte_carlo._eis_schedule(6)
    assert powers == [0, 1, 2, 4, 8, 16]
    assert quantum_monte_carlo._oracle_calls(powers, 100) == sum((2 * k + 1) * 100 for k in powers)


# ---------------------------------------------------------------------------
# CFD / VQLS
# ---------------------------------------------------------------------------
def test_poisson_matrix_is_spd() -> None:
    a = cfd_hybrid.poisson_matrix(8)
    eigenvalues = np.linalg.eigvalsh(a)
    assert np.all(eigenvalues > 0)
    np.testing.assert_allclose(a, a.T)


def test_vqls_cost_zero_at_exact_solution() -> None:
    dim = 8
    a = cfd_hybrid.poisson_matrix(dim)
    b = cfd_hybrid.source_vector(dim, seed=1)
    x = np.linalg.solve(a, b)
    psi = (x / np.linalg.norm(x)).astype(complex)
    assert cfd_hybrid.vqls_cost(psi, a, b) == pytest.approx(0.0, abs=1e-9)


def test_cfd_hybrid_reaches_high_fidelity(sim: LocalStatevectorSimulator) -> None:
    result = cfd_hybrid.run_comparison(
        {"num_qubits": 2, "layers": 3, "max_iterations": 300, "seed": 3},
        sim,
        lambda event: None,
    )
    assert result["paths"]["classical"]["quality"] == 1.0
    assert result["paths"]["hybrid"]["fidelity"] >= 0.95
    assert result["paths"]["hybrid"]["fidelity"] >= result["paths"]["quantum"]["fidelity"]


# ---------------------------------------------------------------------------
# GBS dense subgraph
# ---------------------------------------------------------------------------
def test_hafnian_known_values() -> None:
    # Haf of a 2x2 [[0,w],[w,0]] is w (single matching).
    assert gbs_lifesciences.hafnian(np.array([[0.0, 2.0], [2.0, 0.0]])) == pytest.approx(2.0)
    # 4x4 all-ones off-diagonal: 3 perfect matchings -> haf = 3.
    m = np.ones((4, 4)) - np.eye(4)
    assert gbs_lifesciences.hafnian(m) == pytest.approx(3.0)
    # odd dimension -> 0
    assert gbs_lifesciences.hafnian(np.ones((3, 3))) == 0.0


def test_gbs_distribution_normalized() -> None:
    adjacency = gbs_lifesciences.generate_interaction_graph(6, 0.5, seed=2)
    subsets, dist = gbs_lifesciences._gbs_distribution(adjacency, 4)
    assert len(subsets) == 15  # C(6,4)
    assert dist.sum() == pytest.approx(1.0)
    assert np.all(dist >= 0)


def test_gbs_hybrid_reaches_optimum(sim: LocalStatevectorSimulator) -> None:
    result = gbs_lifesciences.run_comparison(
        {"num_nodes": 8, "subgraph_size": 4, "edge_probability": 0.5, "shots": 500, "seed": 3},
        sim,
        lambda event: None,
    )
    assert result["paths"]["classical"]["quality"] == 1.0
    # GBS + local search should find the exact densest subgraph on this small instance
    assert result["paths"]["hybrid"]["quality"] == pytest.approx(1.0, abs=1e-9)


def test_gbs_rejects_odd_subgraph_size(sim: LocalStatevectorSimulator) -> None:
    with pytest.raises(ValueError):
        gbs_lifesciences.run_comparison({"subgraph_size": 3}, sim, lambda event: None)
