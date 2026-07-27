"""Benchmark engine: classical vs quantum vs hybrid, honestly measured.

Wraps the per-algorithm comparison runners and attaches provenance so the UI
can always tell the user where the numbers came from.
"""

from __future__ import annotations

from typing import Any

from qsolace.algorithms import ProgressCallback, run_comparison
from qsolace.comparison.projection import InfrastructureProfile, project
from qsolace.core.backend import BackendMode, QuantumBackend

#: How to read the "problem size" out of each algorithm's problem dict, so the
#: scaling projection can anchor on it.
_PROBLEM_SIZE_KEY: dict[str, str] = {
    "maxcut-qaoa": "num_nodes",
    "vqe-ising": "num_qubits",
    "gbs-dense-subgraph": "num_nodes",
    "cfd-vqls": "num_qubits",
    "quantum-monte-carlo": "evaluation_levels",
}


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
    result["projection"] = _build_projection(algorithm_id, result)
    result["outcomes"] = classify_outcomes(result["paths"])
    return result


def _quality(path: dict[str, Any]) -> float:
    return float(path.get("approximation_ratio", path.get("quality", 0.0)))


def classify_outcomes(paths: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Rank measured quality separately from modelled quality/cost balance.

    Highest Performance maximizes measured quality (with measured time as a
    deterministic tie-breaker). Optimal Value uses 70% normalized measured
    quality and 30% inverse projected rack cost. The same path can legitimately
    win both; labels are calculated independently rather than applied wholesale.
    """
    profile = InfrastructureProfile()
    keys = ("classical", "quantum", "hybrid")
    qualities = {key: max(_quality(paths[key]), 0.0) for key in keys}
    times = {key: max(float(paths[key]["elapsed_seconds"]), 1e-6) for key in keys}
    costs = {
        key: times[key] * profile.illustrative_rack_cost_per_hour_usd / 3600.0
        for key in keys
    }
    max_quality = max(qualities.values(), default=1.0) or 1.0
    min_cost = min(costs.values())
    scores = {
        key: 0.70 * (qualities[key] / max_quality) + 0.30 * (min_cost / costs[key])
        for key in keys
    }
    performance = max(keys, key=lambda key: (qualities[key], -times[key]))
    value = max(keys, key=lambda key: (scores[key], qualities[key], -times[key]))
    return {
        "highest_performance": performance,
        "optimal_value": value,
        "value_scores": scores,
        "projected_cost_usd": costs,
        "definition": (
            "Highest Performance = maximum measured quality (measured wall time breaks ties). "
            "Optimal Value = 70% normalized measured quality + 30% inverse projected GB300 "
            "rack compute cost at the measured workload. Rack cost is illustrative."
        ),
    }


def _build_projection(algorithm_id: str, result: dict[str, Any]) -> dict[str, Any]:
    paths = result["paths"]
    size_key = _PROBLEM_SIZE_KEY.get(algorithm_id, "num_qubits")
    problem_size = int(result.get("problem", {}).get(size_key, 8))
    measured = {
        "classical_seconds": paths["classical"]["elapsed_seconds"],
        "hybrid_seconds": paths["hybrid"]["elapsed_seconds"],
        "problem_size": problem_size,
    }
    return project(algorithm_id, measured)


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
