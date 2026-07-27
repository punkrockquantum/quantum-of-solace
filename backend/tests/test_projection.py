"""The scaling projection model: crossover and monotonicity behavior."""

import math

import pytest

from qsolace.comparison.engine import classify_outcomes
from qsolace.comparison.projection import (
    InfrastructureProfile,
    ProjectionAssumptions,
    project,
    statevector_memory_tb,
)


def _measured(classical: float, hybrid: float, size: int) -> dict:
    return {"classical_seconds": classical, "hybrid_seconds": hybrid, "problem_size": size}


def test_projection_is_labelled_as_model() -> None:
    proj = project("maxcut-qaoa", _measured(0.01, 0.05, 8))
    assert proj["is_projection"] is True
    assert "PROJECTION" in proj["disclaimer"]


def test_exponential_classical_curve_grows_and_crosses() -> None:
    # hybrid starts slower but classical is exponential -> a crossover must exist
    proj = project("maxcut-qaoa", _measured(0.001, 0.05, 8), ProjectionAssumptions(target_problem_size=40))
    assert proj["crossover_size"] is not None
    first, last = proj["curve"][0], proj["curve"][-1]
    assert last["classical_time"] > first["classical_time"]
    assert last["classical_time"] > last["hybrid_time"]
    assert proj["headline"]["time_speedup"] > 1.0
    assert proj["headline"]["cost_saved_usd"] > 0.0


def test_energy_and_cost_use_assumptions() -> None:
    a = ProjectionAssumptions(hpc_node_power_kw=10.0, energy_cost_per_kwh=0.2, hpc_node_cost_per_hour=4.0)
    proj = project("vqe-ising", _measured(3600.0, 3600.0, 8), a)
    base = proj["curve"][0]
    # at the base size, classical time == 3600s == 1 hour
    assert base["classical_energy"] == pytest.approx(10.0, rel=1e-6)  # 10 kW * 1 h
    assert base["classical_cost"] == pytest.approx(4.0, rel=1e-6)  # $4/node-hr * 1 h


def test_precision_axis_is_bounded_for_monte_carlo() -> None:
    # QMC uses an accuracy-digit axis, not qubits: must not explode to size 40
    proj = project("quantum-monte-carlo", _measured(0.001, 0.002, 6))
    assert proj["size_label"] == "accuracy digits"
    assert proj["target_size"] <= 8
    assert proj["curve"][-1]["size"] <= 8


def test_gb300_profile_matches_cited_nvidia_specs() -> None:
    profile = InfrastructureProfile()
    assert profile.name == "NVIDIA GB300 NVL72"
    assert profile.gpu_count == 72
    assert profile.grace_cpu_count == 36
    assert profile.gpu_memory_tb == 20.0
    assert profile.total_fast_memory_tb == 37.0
    assert profile.nvlink_bandwidth_tbps == 130.0
    assert profile.rack_power_kw == 120.0


def test_latency_targets_include_compute_and_network_separately() -> None:
    fast = project("maxcut-qaoa", _measured(0.001, 0.001, 8), ProjectionAssumptions(target_problem_size=9))
    infra = fast["infrastructure"]
    assert infra["internal_latency"]["meets_target"] is True
    assert infra["end_to_end_latency"]["meets_target"] is True
    assert infra["end_to_end_latency"]["value_ms"] > infra["internal_latency"]["value_ms"]

    slow = project("maxcut-qaoa", _measured(0.1, 0.1, 8), ProjectionAssumptions(target_problem_size=9))
    assert slow["infrastructure"]["internal_latency"]["meets_target"] is False
    assert slow["infrastructure"]["end_to_end_latency"]["meets_target"] is False


def test_statevector_capacity_and_kv_cache_distinction() -> None:
    assert statevector_memory_tb(40) == pytest.approx(17.592186044416)
    proj = project("maxcut-qaoa", _measured(0.01, 0.01, 8), ProjectionAssumptions(target_problem_size=40))
    memory = proj["infrastructure"]["memory"]
    assert memory["required_gpu_memory_tb"] > memory["usable_gpu_memory_tb"]
    assert memory["fits"] is False
    assert "optional co-hosted AI" in proj["infrastructure"]["kv_cache_note"]


def test_outcome_badges_are_independently_scored() -> None:
    paths = {
        "classical": {"approximation_ratio": 1.0, "elapsed_seconds": 10.0},
        "quantum": {"approximation_ratio": 0.8, "elapsed_seconds": 0.01},
        "hybrid": {"approximation_ratio": 0.95, "elapsed_seconds": 1.0},
    }
    outcomes = classify_outcomes(paths)
    assert outcomes["highest_performance"] == "classical"
    assert outcomes["optimal_value"] == "quantum"
    assert "70%" in outcomes["definition"]


def test_projection_numeric_outputs_are_finite() -> None:
    proj = project("maxcut-qaoa", _measured(1e-9, 1e-9, 8))
    values = [
        point[key]
        for point in proj["curve"]
        for key in ("classical_time", "hybrid_time", "classical_energy", "hybrid_energy", "classical_cost", "hybrid_cost")
    ]
    values.extend(proj["headline"].values())
    assert all(math.isfinite(value) for value in values)
