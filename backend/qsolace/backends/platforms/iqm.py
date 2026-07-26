"""IQM superconducting quantum computers.

Connects to IQM Resonance (cloud) or an on-premises IQM system through
``iqm-client``. Circuits in the qsolace IR map directly onto IQM's native
gate set (phased-RX plus CZ) via the client's transpilation.

Configuration (see .env.example):
    QSOLACE_IQM_URL     Server URL (e.g. https://cocos.resonance.meetiqm.com/<qc>)
    QSOLACE_IQM_TOKEN   API token
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class IqmBackend(AdapterBackend):
    ID = "iqm"
    NAME = "IQM"
    VENDOR = "IQM Quantum Computers"
    KIND = BackendKind.PLATFORM
    DESCRIPTION = (
        "Superconducting quantum processors (e.g. IQM Crystal/Star topologies) "
        "via IQM Resonance or on-prem control."
    )
    MAX_QUBITS = 20
    SDK_MODULE = "iqm"
    SDK_INSTALL_HINT = "Install with `pip install iqm-client`."
    REQUIRED_ENV = ("QSOLACE_IQM_URL", "QSOLACE_IQM_TOKEN")
    SETUP_HINT = "Set QSOLACE_IQM_URL and QSOLACE_IQM_TOKEN to attach an IQM system."
