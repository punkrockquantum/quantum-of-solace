"""Shared machinery for hardware/platform/cloud adapters.

Adapters follow a common honesty pattern:

- If the vendor SDK is importable *and* connection config is present, the
  adapter reports ``connected`` and translates circuits to the native API.
- If config is missing, hardware/platform adapters fall back to ``simulated``
  mode: execution is delegated to the exact local statevector simulator, and
  every result is labeled ``simulated=True``.
- Cloud adapters without credentials report ``not_configured`` with setup
  instructions instead of silently simulating.
- If config is present but the SDK is not installed, the adapter reports
  ``unavailable`` with an install hint.
"""

from __future__ import annotations

import importlib.util
import os

from qsolace.core.backend import (
    BackendInfo,
    BackendKind,
    BackendMode,
    BackendUnavailableError,
    ExecutionResult,
    QuantumBackend,
)
from qsolace.core.circuit import Circuit
from qsolace.backends.local_simulator import LocalStatevectorSimulator


def env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def sdk_installed(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


class AdapterBackend(QuantumBackend):
    """Base class for all non-local backends.

    Subclasses define the static metadata below and, when real connectivity
    is implemented, override ``_run_native``.
    """

    # --- static metadata (override in subclasses) ---
    ID: str = ""
    NAME: str = ""
    VENDOR: str = ""
    KIND: BackendKind = BackendKind.PLATFORM
    DESCRIPTION: str = ""
    MAX_QUBITS: int = 20
    #: Python module of the vendor SDK (used to detect installation).
    SDK_MODULE: str = ""
    #: pip install hint shown when the SDK is missing.
    SDK_INSTALL_HINT: str = ""
    #: Environment variables required to attempt a real connection.
    REQUIRED_ENV: tuple[str, ...] = ()
    #: What to tell the user when credentials/config are missing.
    SETUP_HINT: str = ""

    def __init__(self, simulator: LocalStatevectorSimulator | None = None) -> None:
        self._sim = simulator or LocalStatevectorSimulator()

    # ------------------------------------------------------------------
    def _configured(self) -> bool:
        return all(env(v) for v in self.REQUIRED_ENV)

    def _mode(self) -> tuple[BackendMode, str]:
        if self._configured():
            if self.SDK_MODULE and not sdk_installed(self.SDK_MODULE):
                return (
                    BackendMode.UNAVAILABLE,
                    f"Configuration found, but the vendor SDK is not installed. {self.SDK_INSTALL_HINT}",
                )
            return BackendMode.CONNECTED, "Connection configured."
        if self.KIND == BackendKind.CLOUD:
            return BackendMode.NOT_CONFIGURED, self.SETUP_HINT
        return (
            BackendMode.SIMULATED,
            "No device configured - execution is delegated to the exact local "
            f"statevector simulator and labeled as simulation. {self.SETUP_HINT}",
        )

    def info(self) -> BackendInfo:
        mode, detail = self._mode()
        return BackendInfo(
            id=self.ID,
            name=self.NAME,
            vendor=self.VENDOR,
            kind=self.KIND,
            mode=mode,
            description=self.DESCRIPTION,
            max_qubits=self.MAX_QUBITS,
            mode_detail=detail,
        )

    # ------------------------------------------------------------------
    def run(self, circuit: Circuit, shots: int = 1024) -> ExecutionResult:
        mode, detail = self._mode()
        if mode == BackendMode.CONNECTED:
            return self._run_native(circuit, shots)
        if mode == BackendMode.SIMULATED:
            return self._run_delegated(circuit, shots)
        raise BackendUnavailableError(f"{self.NAME}: {detail}")

    def _run_delegated(self, circuit: Circuit, shots: int) -> ExecutionResult:
        result = self._sim.run(circuit, shots)
        return ExecutionResult(
            counts=result.counts,
            shots=shots,
            backend_id=self.ID,
            simulated=True,
            elapsed_seconds=result.elapsed_seconds,
            metadata={
                "method": "exact statevector (delegated)",
                "note": f"No {self.VENDOR} device connected; result computed by the local simulator.",
            },
        )

    def _run_native(self, circuit: Circuit, shots: int) -> ExecutionResult:
        """Translate the circuit to the vendor API and execute on the device.

        Implemented per-adapter as lab integrations land. Until then a
        configured-but-unimplemented adapter fails loudly rather than
        returning fake data.
        """
        raise BackendUnavailableError(
            f"{self.NAME}: native execution is not implemented in this build. "
            "Remove the connection configuration to fall back to simulated mode."
        )
