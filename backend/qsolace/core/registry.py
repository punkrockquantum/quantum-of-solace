"""Registry of available execution backends."""

from __future__ import annotations

from qsolace.core.backend import QuantumBackend


class BackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, QuantumBackend] = {}

    def register(self, backend: QuantumBackend) -> None:
        backend_id = backend.info().id
        if backend_id in self._backends:
            raise ValueError(f"backend '{backend_id}' already registered")
        self._backends[backend_id] = backend

    def get(self, backend_id: str) -> QuantumBackend:
        try:
            return self._backends[backend_id]
        except KeyError:
            raise KeyError(f"unknown backend '{backend_id}'") from None

    def list(self) -> list[QuantumBackend]:
        return list(self._backends.values())
