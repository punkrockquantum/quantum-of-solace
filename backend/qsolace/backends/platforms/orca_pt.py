"""ORCA Computing PT-Series (PT-2) photonic processor.

The PT-Series is a photonic boson-sampling machine programmed through ORCA's
PT-Series SDK (``ptseries``). Its native model is time-bin interferometry
rather than the gate model; ORCA's SDK exposes variational boson-sampling
layers that slot into hybrid workflows in exactly the same optimizer loop
this orchestrator uses. Until a PT-2 is attached, gate-model workloads are
delegated to the local simulator and labeled as simulation.

Configuration (see .env.example):
    QSOLACE_ORCA_URL     PT-Series control server URL
    QSOLACE_ORCA_TOKEN   Access token
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class OrcaPtSeriesBackend(AdapterBackend):
    ID = "orca-pt2"
    NAME = "ORCA PT-2"
    VENDOR = "ORCA Computing"
    KIND = BackendKind.PLATFORM
    DESCRIPTION = (
        "Photonic time-bin boson sampler (PT-Series). Native workloads are "
        "variational boson-sampling layers driven by the same hybrid loop."
    )
    MAX_QUBITS = 8
    SDK_MODULE = "ptseries"
    SDK_INSTALL_HINT = "Install ORCA's PT-Series SDK on the control host."
    REQUIRED_ENV = ("QSOLACE_ORCA_URL", "QSOLACE_ORCA_TOKEN")
    SETUP_HINT = "Set QSOLACE_ORCA_URL and QSOLACE_ORCA_TOKEN to attach a PT-2."
