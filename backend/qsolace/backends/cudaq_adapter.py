"""NVIDIA CUDA-Q adapter.

CUDA-Q (``cudaq``) provides GPU-accelerated statevector/tensor-network
simulation and is the intended lab execution engine for the heavy lift of
hybrid workflows. The Python wheels are Linux-only, so on macOS development
machines this adapter reports ``unavailable`` and the orchestrator uses the
exact local simulator instead - the workflow code is identical either way.
"""

from __future__ import annotations

import time

from qsolace.core.backend import (
    BackendInfo,
    BackendKind,
    BackendMode,
    BackendUnavailableError,
    ExecutionResult,
    QuantumBackend,
)
from qsolace.core.circuit import Circuit
from qsolace.backends._base import sdk_installed


class CudaQBackend(QuantumBackend):
    MAX_QUBITS = 30

    def __init__(self) -> None:
        self._available = sdk_installed("cudaq")

    def info(self) -> BackendInfo:
        if self._available:
            mode = BackendMode.CONNECTED
            detail = "CUDA-Q runtime detected. Circuits run on the default cudaq target."
        else:
            mode = BackendMode.UNAVAILABLE
            detail = (
                "The cudaq package is not installed on this host (wheels are "
                "Linux-only). In the lab, `pip install cudaq` on a Linux/GPU "
                "node activates this backend with no other changes."
            )
        return BackendInfo(
            id="cuda-q",
            name="NVIDIA CUDA-Q",
            vendor="NVIDIA",
            kind=BackendKind.SIMULATOR,
            mode=mode,
            description=(
                "GPU-accelerated quantum kernel execution for HPC-scale hybrid "
                "workflows (statevector and tensor-network targets)."
            ),
            max_qubits=self.MAX_QUBITS,
            mode_detail=detail,
        )

    def run(self, circuit: Circuit, shots: int = 1024) -> ExecutionResult:
        if not self._available:
            raise BackendUnavailableError(
                "CUDA-Q is not installed on this host. Use the local simulator, "
                "or run on a Linux node with `pip install cudaq`."
            )
        return self._run_cudaq(circuit, shots)

    def _run_cudaq(self, circuit: Circuit, shots: int) -> ExecutionResult:
        import cudaq  # noqa: PLC0415 - optional dependency

        start = time.perf_counter()
        kernel = cudaq.make_kernel()
        qubits = kernel.qalloc(circuit.num_qubits)

        for gate in circuit.gates:
            name, q, params = gate.name, gate.qubits, gate.params
            if name in ("h", "x", "y", "z", "s", "t"):
                getattr(kernel, name)(qubits[q[0]])
            elif name == "sdg":
                kernel.rz(-3.141592653589793 / 2.0, qubits[q[0]])
            elif name in ("rx", "ry", "rz"):
                getattr(kernel, name)(params[0], qubits[q[0]])
            elif name == "cx":
                kernel.cx(qubits[q[0]], qubits[q[1]])
            elif name == "cz":
                kernel.cz(qubits[q[0]], qubits[q[1]])
            elif name == "swap":
                kernel.swap(qubits[q[0]], qubits[q[1]])
            elif name == "rzz":
                # exp(-i theta/2 Z Z) = CX . RZ(theta) . CX
                kernel.cx(qubits[q[0]], qubits[q[1]])
                kernel.rz(params[0], qubits[q[1]])
                kernel.cx(qubits[q[0]], qubits[q[1]])
            else:  # pragma: no cover
                raise ValueError(f"unsupported gate '{name}'")

        sample = cudaq.sample(kernel, shots_count=shots)
        elapsed = time.perf_counter() - start
        # cudaq bitstrings index qubit 0 first, matching our convention.
        counts = {bits: count for bits, count in sample.items()}
        return ExecutionResult(
            counts=counts,
            shots=shots,
            backend_id="cuda-q",
            simulated=True,
            elapsed_seconds=elapsed,
            metadata={"method": "cudaq.sample", "target": str(cudaq.get_target().name)},
        )
