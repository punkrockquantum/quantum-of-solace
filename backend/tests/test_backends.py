"""Backend registry and adapter honesty guarantees."""

import pytest

from qsolace.backends.factory import create_default_registry
from qsolace.core.backend import BackendMode, BackendUnavailableError
from qsolace.core.circuit import Circuit

EXPECTED_BACKENDS = {
    "local-simulator",
    "cuda-q",
    "qick-rfsoc",
    "quantum-machines",
    "qblox",
    "orca-pt2",
    "iqm",
    "atom-computing",
    "quera",
    "aws-braket",
    "strangeworks",
}


@pytest.fixture()
def registry():
    return create_default_registry(seed=1)


def test_all_backends_registered(registry) -> None:
    assert {b.info().id for b in registry.list()} == EXPECTED_BACKENDS


def test_hardware_adapters_simulate_without_config(registry, monkeypatch) -> None:
    for var in ("QSOLACE_QICK_HOST", "QSOLACE_QM_HOST", "QSOLACE_QBLOX_HOST"):
        monkeypatch.delenv(var, raising=False)
    for backend_id in ("qick-rfsoc", "quantum-machines", "qblox", "orca-pt2", "iqm"):
        backend = registry.get(backend_id)
        info = backend.info()
        assert info.mode == BackendMode.SIMULATED, backend_id
        result = backend.run(Circuit(2).h(0).cx(0, 1), shots=100)
        # honesty contract: delegated results are labeled as simulation
        assert result.simulated is True
        assert result.backend_id == backend_id
        assert sum(result.counts.values()) == 100


def test_cloud_adapters_require_credentials(registry, monkeypatch) -> None:
    monkeypatch.delenv("STRANGEWORKS_API_KEY", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    for backend_id in ("aws-braket", "strangeworks"):
        backend = registry.get(backend_id)
        assert backend.info().mode == BackendMode.NOT_CONFIGURED
        with pytest.raises(BackendUnavailableError):
            backend.run(Circuit(1).h(0))


def test_configured_but_missing_sdk_is_unavailable(registry, monkeypatch) -> None:
    monkeypatch.setenv("STRANGEWORKS_API_KEY", "test-placeholder-key")
    backend = registry.get("strangeworks")
    info = backend.info()
    # the strangeworks SDK is not installed in the test environment
    assert info.mode == BackendMode.UNAVAILABLE
    with pytest.raises(BackendUnavailableError):
        backend.run(Circuit(1).h(0))


def test_unknown_backend_raises(registry) -> None:
    with pytest.raises(KeyError):
        registry.get("does-not-exist")
