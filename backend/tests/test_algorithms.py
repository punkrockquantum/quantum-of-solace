"""Algorithm correctness against exactly known optima."""

import numpy as np
import pytest

from qsolace.algorithms import maxcut_qaoa, vqe_ising
from qsolace.backends.local_simulator import LocalStatevectorSimulator


@pytest.fixture()
def sim() -> LocalStatevectorSimulator:
    return LocalStatevectorSimulator(seed=11)


# ---------------------------------------------------------------------------
# Max-Cut
# ---------------------------------------------------------------------------
def test_cut_values_triangle() -> None:
    # triangle graph: any 2-1 split cuts exactly 2 of the 3 edges
    edges = [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 1.0)]
    values = maxcut_qaoa.cut_values(3, edges)
    assert values.max() == 2.0
    assert values[0] == 0.0  # all nodes on one side -> nothing cut
    assert values[-1] == 0.0


def test_cut_values_square_cycle() -> None:
    # 4-cycle: alternating partition cuts all 4 edges
    edges = [(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0), (0, 3, 1.0)]
    values = maxcut_qaoa.cut_values(4, edges)
    assert values.max() == 4.0
    # partition 0101 (nodes 0,2 vs 1,3) -> index 0b1010 = 10
    assert values[0b1010] == 4.0


def test_qaoa_hybrid_converges_to_optimum(sim: LocalStatevectorSimulator) -> None:
    result = maxcut_qaoa.run_comparison(
        {"num_nodes": 6, "edge_probability": 0.5, "layers": 2, "max_iterations": 60, "seed": 3},
        sim,
        lambda event: None,
    )
    assert result["paths"]["classical"]["approximation_ratio"] == 1.0
    # hybrid should find a (near-)optimal cut on this small seeded instance
    assert result["paths"]["hybrid"]["approximation_ratio"] >= 0.9
    # the optimizer must actually improve over the starting expectation
    history = result["paths"]["hybrid"]["history"]
    assert history[-1]["best"] > history[0]["expected_cut"]


# ---------------------------------------------------------------------------
# VQE / transverse-field Ising
# ---------------------------------------------------------------------------
def test_hamiltonian_two_spins_analytic() -> None:
    # H = -J Z0 Z1 - h(X0 + X1) has exact ground energy -sqrt(J^2 + 4 h^2)
    j, h = 1.0, 1.0
    hamiltonian = vqe_ising.build_hamiltonian(2, j, h)
    ground = float(np.linalg.eigvalsh(hamiltonian)[0])
    assert ground == pytest.approx(-np.sqrt(j**2 + 4 * h**2), abs=1e-10)


def test_hamiltonian_is_hermitian() -> None:
    hamiltonian = vqe_ising.build_hamiltonian(4, 1.3, 0.7)
    np.testing.assert_allclose(hamiltonian, hamiltonian.T.conj())


def test_vqe_hybrid_reaches_ground_state(sim: LocalStatevectorSimulator) -> None:
    result = vqe_ising.run_comparison(
        {"num_qubits": 4, "layers": 2, "max_iterations": 150, "seed": 3},
        sim,
        lambda event: None,
    )
    exact = result["optimal"]["energy"]
    hybrid = result["paths"]["hybrid"]
    # variational principle: measured energy can never undercut the true ground energy
    assert hybrid["energy"] >= exact - 1e-9
    # and the optimizer should get close to it
    assert hybrid["quality"] >= 0.98
    # hybrid must beat unoptimized quantum sampling
    assert hybrid["energy"] <= result["paths"]["quantum"]["energy"] + 1e-9


def test_vqe_energy_measurement_exact_vs_sampled(sim: LocalStatevectorSimulator) -> None:
    """The counts-based (hardware-path) energy estimator must agree with the
    exact statevector estimator within shot noise."""

    class CountsOnly:
        """Wrapper hiding the statevector so the sampled path is exercised."""

        def __init__(self, inner: LocalStatevectorSimulator) -> None:
            self._inner = inner

        def run(self, circuit, shots=1024):
            return self._inner.run(circuit, shots)

    rng = np.random.default_rng(5)
    theta = rng.uniform(-np.pi, np.pi, size=vqe_ising.num_parameters(3, 1))
    hamiltonian = vqe_ising.build_hamiltonian(3, 1.0, 1.0)

    exact = vqe_ising.measure_energy(sim, 3, 1, theta, 1.0, 1.0, hamiltonian, shots=0)
    sampled = vqe_ising.measure_energy(CountsOnly(sim), 3, 1, theta, 1.0, 1.0, hamiltonian, shots=20000)
    assert sampled == pytest.approx(exact, abs=0.15)
