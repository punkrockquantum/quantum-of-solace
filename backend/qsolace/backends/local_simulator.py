"""Exact statevector simulator built on NumPy.

This is the fully functional demo workhorse. It performs exact unitary
evolution of the full 2^n statevector, so all probabilities, samples, and
expectation values are mathematically exact (up to float64 precision).
"""

from __future__ import annotations

import time

import numpy as np

from qsolace.core.backend import (
    BackendInfo,
    BackendKind,
    BackendMode,
    ExecutionResult,
    QuantumBackend,
)
from qsolace.core.circuit import Circuit

_SQ2 = 1.0 / np.sqrt(2.0)

_FIXED_1Q = {
    "h": np.array([[_SQ2, _SQ2], [_SQ2, -_SQ2]], dtype=complex),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "z": np.array([[1, 0], [0, -1]], dtype=complex),
    "s": np.array([[1, 0], [0, 1j]], dtype=complex),
    "sdg": np.array([[1, 0], [0, -1j]], dtype=complex),
    "t": np.array([[1, 0], [0, np.exp(1j * np.pi / 4)]], dtype=complex),
}


def _rotation_1q(name: str, theta: float) -> np.ndarray:
    c, s = np.cos(theta / 2.0), np.sin(theta / 2.0)
    if name == "rx":
        return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
    if name == "ry":
        return np.array([[c, -s], [s, c]], dtype=complex)
    if name == "rz":
        return np.array([[np.exp(-1j * theta / 2.0), 0], [0, np.exp(1j * theta / 2.0)]], dtype=complex)
    raise ValueError(name)


class LocalStatevectorSimulator(QuantumBackend):
    """Exact dense statevector simulation, practical up to ~20 qubits."""

    MAX_QUBITS = 20

    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)

    def info(self) -> BackendInfo:
        return BackendInfo(
            id="local-simulator",
            name="Local statevector simulator",
            vendor="Quantum of Solace",
            kind=BackendKind.SIMULATOR,
            mode=BackendMode.CONNECTED,
            description=(
                "Exact NumPy statevector simulation running on this machine. "
                "All results are mathematically exact."
            ),
            max_qubits=self.MAX_QUBITS,
            mode_detail="Ready. Exact simulation, no noise model.",
        )

    # ------------------------------------------------------------------
    # Core simulation
    # ------------------------------------------------------------------
    def statevector(self, circuit: Circuit) -> np.ndarray:
        """Return the final statevector as a flat array of 2^n amplitudes.

        Qubit ``i`` corresponds to bit ``i`` of the basis-state index
        (little-endian), matching the bitstring convention of
        ``ExecutionResult.counts``.
        """
        n = circuit.num_qubits
        if n > self.MAX_QUBITS:
            raise ValueError(f"{n} qubits exceeds simulator limit of {self.MAX_QUBITS}")
        # state tensor with one axis per qubit; axis i == qubit i
        state = np.zeros((2,) * n, dtype=complex)
        state[(0,) * n] = 1.0

        for gate in circuit.gates:
            if gate.name in _FIXED_1Q:
                state = self._apply_1q(state, _FIXED_1Q[gate.name], gate.qubits[0])
            elif gate.name in ("rx", "ry", "rz"):
                state = self._apply_1q(state, _rotation_1q(gate.name, gate.params[0]), gate.qubits[0])
            elif gate.name == "cx":
                state = self._apply_2q(state, self._cx_matrix(), gate.qubits[0], gate.qubits[1])
            elif gate.name == "cz":
                state = self._apply_2q(state, np.diag([1, 1, 1, -1]).astype(complex), gate.qubits[0], gate.qubits[1])
            elif gate.name == "swap":
                state = np.swapaxes(state, gate.qubits[0], gate.qubits[1])
            elif gate.name == "rzz":
                theta = gate.params[0]
                u = np.diag(
                    [
                        np.exp(-1j * theta / 2.0),
                        np.exp(1j * theta / 2.0),
                        np.exp(1j * theta / 2.0),
                        np.exp(-1j * theta / 2.0),
                    ]
                )
                state = self._apply_2q(state, u, gate.qubits[0], gate.qubits[1])
            else:  # pragma: no cover - Gate validation prevents this
                raise ValueError(f"unsupported gate '{gate.name}'")

        # Flatten so that bit i of the index corresponds to qubit i.
        # Axis 0 (qubit 0) must be the fastest-varying index -> reverse axes.
        return np.transpose(state, axes=range(n - 1, -1, -1)).reshape(-1)

    @staticmethod
    def _apply_1q(state: np.ndarray, u: np.ndarray, qubit: int) -> np.ndarray:
        moved = np.tensordot(u, state, axes=[[1], [qubit]])  # new axis 0 = qubit
        return np.moveaxis(moved, 0, qubit)

    @staticmethod
    def _apply_2q(state: np.ndarray, u4: np.ndarray, q0: int, q1: int) -> np.ndarray:
        # u4 is 4x4 in basis |q0 q1> with q0 the most significant bit.
        u = u4.reshape(2, 2, 2, 2)  # [q0', q1', q0, q1]
        moved = np.tensordot(u, state, axes=[[2, 3], [q0, q1]])  # axes 0,1 = q0', q1'
        return np.moveaxis(moved, [0, 1], [q0, q1])

    @staticmethod
    def _cx_matrix() -> np.ndarray:
        # control = first qubit (most significant in the 4x4 basis)
        return np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
                [0, 0, 1, 0],
            ],
            dtype=complex,
        )

    def probabilities(self, circuit: Circuit) -> np.ndarray:
        amps = self.statevector(circuit)
        probs = np.abs(amps) ** 2
        return probs / probs.sum()

    # ------------------------------------------------------------------
    # QuantumBackend interface
    # ------------------------------------------------------------------
    def run(self, circuit: Circuit, shots: int = 1024) -> ExecutionResult:
        start = time.perf_counter()
        probs = self.probabilities(circuit)
        samples = self._rng.choice(len(probs), size=shots, p=probs)
        elapsed = time.perf_counter() - start

        n = circuit.num_qubits
        counts: dict[str, int] = {}
        for index, count in zip(*np.unique(samples, return_counts=True)):
            # little-endian bitstring: character i == qubit i
            bitstring = "".join(str((int(index) >> q) & 1) for q in range(n))
            counts[bitstring] = int(count)

        return ExecutionResult(
            counts=counts,
            shots=shots,
            backend_id=self.info().id,
            simulated=True,
            elapsed_seconds=elapsed,
            metadata={"method": "exact statevector"},
        )
