"""Benchmark engine: classical vs quantum vs hybrid, honestly measured.

Wraps the per-algorithm comparison runners and attaches provenance so the UI
can always tell the user where the numbers came from.
"""

from __future__ import annotations

from typing import Any

from qsolace.algorithms import ProgressCallback, run_comparison
from qsolace.core.backend import BackendMode, QuantumBackend


def run_benchmark(
    algorithm_id: str,
    params: dict[str, Any],
    backend: QuantumBackend,
    progress: ProgressCallback,
) -> dict[str, Any]:
    info = backend.info()
    result = run_comparison(algorithm_id, params, backend, progress)

    result["provenance"] = {
        "backend_id": info.id,
        "backend_name": info.name,
        "backend_mode": info.mode.value,
        "simulated": info.mode != BackendMode.CONNECTED or info.kind.value == "simulator",
        "statement": _provenance_statement(info),
    }
    return result


def _provenance_statement(info) -> str:
    if info.kind.value == "simulator":
        return (
            f"Quantum results computed by exact simulation on {info.name}. "
            "All values are mathematically exact expectations or fair samples "
            "from the true output distribution."
        )
    if info.mode == BackendMode.CONNECTED:
        return f"Quantum results measured on real hardware via {info.name}."
    return (
        f"{info.name} has no device attached; quantum results were computed by "
        "the exact local statevector simulator and are labeled as simulation."
    )
