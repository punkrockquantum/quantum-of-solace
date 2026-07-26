"""The unified backend interface every execution target implements.

A backend may be a local simulator, a GPU-accelerated CUDA-Q target,
lab control hardware (QICK/RFSoC, Quantum Machines, QBLOX), a vendor
platform (ORCA, IQM, Atom Computing, QuEra), or a cloud service
(AWS Braket, Strangeworks).

Honesty contract: every backend reports a ``BackendMode`` describing where
results actually come from, and every ``ExecutionResult`` carries a
``simulated`` flag. Nothing in the stack may present simulated data as
hardware data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from qsolace.core.circuit import Circuit


class BackendKind(str, Enum):
    SIMULATOR = "simulator"
    CONTROL_HARDWARE = "control_hardware"
    PLATFORM = "platform"
    CLOUD = "cloud"


class BackendMode(str, Enum):
    #: Real device or remote service is reachable; results are real.
    CONNECTED = "connected"
    #: Driver present but no device attached; execution is delegated to the
    #: local statevector simulator and labeled as simulation.
    SIMULATED = "simulated"
    #: Credentials/config missing (cloud backends).
    NOT_CONFIGURED = "not_configured"
    #: Required SDK is not installed on this host.
    UNAVAILABLE = "unavailable"


@dataclass
class BackendInfo:
    id: str
    name: str
    vendor: str
    kind: BackendKind
    mode: BackendMode
    description: str
    max_qubits: int
    #: Human-readable note about the current mode (e.g. setup instructions).
    mode_detail: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "kind": self.kind.value,
            "mode": self.mode.value,
            "description": self.description,
            "max_qubits": self.max_qubits,
            "mode_detail": self.mode_detail,
        }


@dataclass
class ExecutionResult:
    """Result of executing one circuit for ``shots`` measurement samples."""

    #: bitstring -> observed count; bitstrings are little-endian
    #: (character i corresponds to qubit i).
    counts: dict[str, int]
    shots: int
    backend_id: str
    #: True whenever the numbers come from simulation rather than hardware.
    simulated: bool
    elapsed_seconds: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "shots": self.shots,
            "backend_id": self.backend_id,
            "simulated": self.simulated,
            "elapsed_seconds": self.elapsed_seconds,
            "metadata": self.metadata,
        }


class QuantumBackend(ABC):
    """Abstract execution target."""

    @abstractmethod
    def info(self) -> BackendInfo:
        """Static description plus current connectivity mode."""

    @abstractmethod
    def run(self, circuit: Circuit, shots: int = 1024) -> ExecutionResult:
        """Execute ``circuit`` and return measurement counts.

        Must raise ``BackendUnavailableError`` if the backend cannot execute
        in its current mode.
        """

    @property
    def id(self) -> str:
        return self.info().id


class BackendUnavailableError(RuntimeError):
    """Raised when a backend cannot execute in its current mode."""
