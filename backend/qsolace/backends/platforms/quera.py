"""QuEra neutral-atom (Rydberg) quantum computers.

QuEra Aquila is an analog neutral-atom machine programmed as Rydberg
Hamiltonian schedules (e.g. via Bloqade), and is also reachable through AWS
Braket. This adapter covers direct access; the Braket adapter covers the
cloud route. Analog Hamiltonian workloads plug into the same hybrid
optimizer loop as gate-model backends.

Configuration (see .env.example):
    QSOLACE_QUERA_TOKEN   Direct-access token
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class QuEraBackend(AdapterBackend):
    ID = "quera"
    NAME = "QuEra"
    VENDOR = "QuEra Computing"
    KIND = BackendKind.PLATFORM
    DESCRIPTION = (
        "Analog neutral-atom (Rydberg) processors; native workloads are "
        "Hamiltonian schedules (Bloqade-style), also reachable via AWS Braket."
    )
    MAX_QUBITS = 20
    SDK_MODULE = "bloqade"
    SDK_INSTALL_HINT = "Install with `pip install bloqade-analog`."
    REQUIRED_ENV = ("QSOLACE_QUERA_TOKEN",)
    SETUP_HINT = "Set QSOLACE_QUERA_TOKEN for direct access, or use the AWS Braket backend."
