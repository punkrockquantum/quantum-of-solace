"""Strangeworks quantum cloud platform.

Strangeworks aggregates hardware and simulator providers behind one API and
billing surface, accessed through the ``strangeworks`` SDK.

Configuration (see .env.example):
    STRANGEWORKS_API_KEY   Workspace API key from portal.strangeworks.com
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class StrangeworksBackend(AdapterBackend):
    ID = "strangeworks"
    NAME = "Strangeworks"
    VENDOR = "Strangeworks"
    KIND = BackendKind.CLOUD
    DESCRIPTION = (
        "Aggregated access to multiple quantum hardware and simulator "
        "providers through the Strangeworks platform."
    )
    MAX_QUBITS = 30
    SDK_MODULE = "strangeworks"
    SDK_INSTALL_HINT = "Install with `pip install strangeworks`."
    REQUIRED_ENV = ("STRANGEWORKS_API_KEY",)
    SETUP_HINT = (
        "Set STRANGEWORKS_API_KEY (from portal.strangeworks.com) and install "
        "the `strangeworks` SDK."
    )
