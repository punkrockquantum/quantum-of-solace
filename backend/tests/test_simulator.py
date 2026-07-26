"""Correctness of the statevector simulator against known quantum states."""

import numpy as np
import pytest

from qsolace.backends.local_simulator import LocalStatevectorSimulator
from qsolace.core.circuit import Circuit


@pytest.fixture()
def sim() -> LocalStatevectorSimulator:
    return LocalStatevectorSimulator(seed=42)


def test_bell_state_amplitudes(sim: LocalStatevectorSimulator) -> None:
    circuit = Circuit(2).h(0).cx(0, 1)
    amplitudes = sim.statevector(circuit)
    expected = np.array([1, 0, 0, 1]) / np.sqrt(2)
    np.testing.assert_allclose(amplitudes, expected, atol=1e-12)


def test_bell_state_counts_split(sim: LocalStatevectorSimulator) -> None:
    circuit = Circuit(2).h(0).cx(0, 1)
    result = sim.run(circuit, shots=8000)
    assert set(result.counts) == {"00", "11"}
    assert result.simulated is True
    # fair sampling: both outcomes near 50% (loose 5-sigma bound)
    assert abs(result.counts["00"] - 4000) < 5 * np.sqrt(2000)


def test_little_endian_convention(sim: LocalStatevectorSimulator) -> None:
    # X on qubit 1 of 3 -> basis index 2 (bit 1 set), bitstring "010"
    circuit = Circuit(3).x(1)
    probs = sim.probabilities(circuit)
    assert int(np.argmax(probs)) == 2
    result = sim.run(circuit, shots=10)
    assert result.counts == {"010": 10}


def test_ghz_state(sim: LocalStatevectorSimulator) -> None:
    circuit = Circuit(3).h(0).cx(0, 1).cx(1, 2)
    result = sim.run(circuit, shots=2000)
    assert set(result.counts) == {"000", "111"}


def test_rzz_equals_cx_rz_cx_decomposition(sim: LocalStatevectorSimulator) -> None:
    theta = 0.731
    direct = Circuit(2).h(0).h(1).rzz(theta, 0, 1)
    decomposed = Circuit(2).h(0).h(1).cx(0, 1).rz(theta, 1).cx(0, 1)
    np.testing.assert_allclose(sim.statevector(direct), sim.statevector(decomposed), atol=1e-12)


def test_statevector_normalized(sim: LocalStatevectorSimulator) -> None:
    rng = np.random.default_rng(0)
    circuit = Circuit(4)
    for q in range(4):
        circuit.ry(rng.uniform(0, np.pi), q)
    for q in range(3):
        circuit.cx(q, q + 1)
    amplitudes = sim.statevector(circuit)
    assert np.abs(np.linalg.norm(amplitudes) - 1.0) < 1e-12


def test_qubit_limit_enforced(sim: LocalStatevectorSimulator) -> None:
    with pytest.raises(ValueError):
        sim.statevector(Circuit(25))
