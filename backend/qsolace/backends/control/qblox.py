"""QBLOX Cluster control stack.

Connects to a QBLOX Cluster (QCM/QRM modules) through ``qblox-instruments``.
Circuit-level jobs are lowered to Q1ASM sequences; pulse calibration data is
expected from the lab's setup (e.g. via quantify-scheduler).

Configuration (see .env.example):
    QSOLACE_QBLOX_HOST   IP/hostname of the cluster management port
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class QbloxBackend(AdapterBackend):
    ID = "qblox"
    NAME = "QBLOX Cluster"
    VENDOR = "QBLOX"
    KIND = BackendKind.CONTROL_HARDWARE
    DESCRIPTION = (
        "Modular qubit control and readout with a QBLOX Cluster; circuits are "
        "lowered to Q1ASM sequencer programs."
    )
    MAX_QUBITS = 10
    SDK_MODULE = "qblox_instruments"
    SDK_INSTALL_HINT = "Install with `pip install qblox-instruments`."
    REQUIRED_ENV = ("QSOLACE_QBLOX_HOST",)
    SETUP_HINT = "Set QSOLACE_QBLOX_HOST to attach a cluster."
