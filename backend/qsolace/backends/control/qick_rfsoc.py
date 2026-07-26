"""RFSoC control stack via QICK (Quantum Instrumentation Control Kit).

Targets AMD Xilinx ZCU111 / ZCU216 evaluation boards running the open-source
QICK firmware. In the lab, the board runs a Pyro4 server exposing the QICK
``QickSoc`` object; this adapter connects to it and compiles circuit-level
programs into qick pulse programs (via qick's averager programs).

Configuration (see .env.example):
    QSOLACE_QICK_HOST   IP/hostname of the RFSoC board's Pyro4 server
    QSOLACE_QICK_BOARD  zcu111 | zcu216
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend, env
from qsolace.core.backend import BackendKind


class QickRfsocBackend(AdapterBackend):
    ID = "qick-rfsoc"
    NAME = "RFSoC (QICK / ZCU111-ZCU216)"
    VENDOR = "AMD Xilinx / QICK"
    KIND = BackendKind.CONTROL_HARDWARE
    DESCRIPTION = (
        "Direct pulse-level qubit control on AMD Xilinx RFSoC boards "
        "(ZCU111 / ZCU216) running the open-source QICK firmware."
    )
    MAX_QUBITS = 8
    SDK_MODULE = "qick"
    SDK_INSTALL_HINT = "Install with `pip install qick` on the control host."
    REQUIRED_ENV = ("QSOLACE_QICK_HOST",)
    SETUP_HINT = "Set QSOLACE_QICK_HOST (and QSOLACE_QICK_BOARD) to attach a board."

    def info(self):
        base = super().info()
        board = env("QSOLACE_QICK_BOARD") or "zcu216"
        base.description = f"{self.DESCRIPTION} Selected board profile: {board.upper()}."
        return base
