"""AWS Braket cloud service.

Provides access to simulators (SV1/DM1/TN1) and hardware partners (IonQ,
Rigetti, IQM, QuEra Aquila) through the ``amazon-braket-sdk``. Credentials
come from the standard AWS credential chain; the target device is selected
with QSOLACE_BRAKET_DEVICE_ARN.

Configuration (see .env.example):
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
    QSOLACE_BRAKET_DEVICE_ARN   e.g. arn:aws:braket:::device/quantum-simulator/amazon/sv1
"""

from __future__ import annotations

from qsolace.backends._base import AdapterBackend
from qsolace.core.backend import BackendKind


class BraketBackend(AdapterBackend):
    ID = "aws-braket"
    NAME = "AWS Braket"
    VENDOR = "Amazon Web Services"
    KIND = BackendKind.CLOUD
    DESCRIPTION = (
        "Managed access to cloud simulators (SV1, DM1, TN1) and hardware "
        "partners (IonQ, Rigetti, IQM, QuEra) through Amazon Braket."
    )
    MAX_QUBITS = 34
    SDK_MODULE = "braket"
    SDK_INSTALL_HINT = "Install with `pip install amazon-braket-sdk`."
    REQUIRED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "QSOLACE_BRAKET_DEVICE_ARN")
    SETUP_HINT = (
        "Set AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
        "AWS_DEFAULT_REGION) and QSOLACE_BRAKET_DEVICE_ARN, then install "
        "`amazon-braket-sdk`."
    )
