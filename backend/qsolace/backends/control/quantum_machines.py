"""Quantum Machines OPX control stack.

Connects to a Quantum Machines QOP cluster (OPX+/OPX1000) via the ``qm``
Python SDK. Circuit-level jobs are compiled into QUA programs; pulse
calibrations are expected to be provided by the lab's QUA configuration.

Configuration (see .env.example):
    QSOLACE_QM_HOST   IP/hostname of the QOP cluster
    QSOLACE_QM_PORT   Gateway port (default 9510)
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class QuantumMachinesBackend(AdapterBackend):
    ID = "quantum-machines"
    NAME = "Quantum Machines OPX"
    VENDOR = "Quantum Machines"
    KIND = BackendKind.CONTROL_HARDWARE
    DESCRIPTION = (
        "Real-time control of superconducting/spin qubits through a Quantum "
        "Machines OPX cluster; circuits are compiled to QUA programs."
    )
    MAX_QUBITS = 10
    SDK_MODULE = "qm"
    SDK_INSTALL_HINT = "Install with `pip install qm-qua`."
    REQUIRED_ENV = ("QSOLACE_QM_HOST",)
    SETUP_HINT = "Set QSOLACE_QM_HOST (and QSOLACE_QM_PORT) to attach a cluster."
