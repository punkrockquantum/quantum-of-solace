"""The scaling projection model: crossover and monotonicity behavior."""

import pytest

from qsolace.comparison.projection import ProjectionAssumptions, project


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
