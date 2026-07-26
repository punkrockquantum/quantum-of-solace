"""Atom Computing neutral-atom quantum computers.

Atom Computing's Phoenix-class systems use optically trapped neutral atoms
with long-lived nuclear spin qubits. Access is via Atom Computing's API
gateway. Until access is provisioned, workloads are delegated to the local
simulator and labeled as simulation.

Configuration (see .env.example):
    QSOLACE_ATOM_URL     API endpoint
    QSOLACE_ATOM_TOKEN   Access token
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class AtomComputingBackend(AdapterBackend):
    ID = "atom-computing"
    NAME = "Atom Computing"
    VENDOR = "Atom Computing"
    KIND = BackendKind.PLATFORM
    DESCRIPTION = (
        "Neutral-atom (nuclear spin qubit) quantum processors with "
        "atom-array scaling."
    )
    MAX_QUBITS = 20
    SDK_MODULE = ""  # access via HTTP API gateway
    SDK_INSTALL_HINT = ""
    REQUIRED_ENV = ("QSOLACE_ATOM_URL", "QSOLACE_ATOM_TOKEN")
    SETUP_HINT = "Set QSOLACE_ATOM_URL and QSOLACE_ATOM_TOKEN to attach a system."
