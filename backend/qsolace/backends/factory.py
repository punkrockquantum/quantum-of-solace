"""Default backend registry used by the API server and the CLI/tests."""

from __future__ import annotations

from qsolace.core.registry import BackendRegistry
from qsolace.backends.local_simulator import LocalStatevectorSimulator
from qsolace.backends.cudaq_adapter import CudaQBackend
from qsolace.backends.control import QbloxBackend, QickRfsocBackend, QuantumMachinesBackend
from qsolace.backends.platforms import (
    AtomComputingBackend,
    IqmBackend,
    OrcaPtSeriesBackend,
    QuEraBackend,
)
from qsolace.backends.cloud import BraketBackend, StrangeworksBackend


def create_default_registry(seed: int | None = None) -> BackendRegistry:
    registry = BackendRegistry()
    simulator = LocalStatevectorSimulator(seed=seed)
    registry.register(simulator)
    registry.register(CudaQBackend())
    # All adapters share the simulator instance for delegated (simulated) runs.
    for adapter_cls in (
        QickRfsocBackend,
        QuantumMachinesBackend,
        QbloxBackend,
        OrcaPtSeriesBackend,
        IqmBackend,
        AtomComputingBackend,
        QuEraBackend,
        BraketBackend,
        StrangeworksBackend,
    ):
        registry.register(adapter_cls(simulator=simulator))
    return registry
