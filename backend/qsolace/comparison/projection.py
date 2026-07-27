"""Scaling projection: turning a measured per-instance result into an upside.

IMPORTANT: everything this module produces is a TRANSPARENT MODEL / EXTRAPOLATION,
not a measurement. It anchors on the *measured* wall times of this run and
projects forward using stated complexity assumptions and stated cost/energy
figures. It is clearly separated from measured results everywhere it surfaces.

The story it quantifies is the one that motivates hybrid quantum computing: at
small sizes an exact classical method is cheap and usually wins outright, but
its cost grows with a steep (often exponential) complexity curve while a hybrid
quantum workflow's cost per instance grows polynomially. Past a crossover
problem size the hybrid workflow wins, and because the classical curve is
super-polynomial the advantage compounds into large savings in time, energy,
cost, and -- given a value per solved instance -- profit.

All assumptions live in ``ProjectionAssumptions`` so they can be inspected and
adjusted. Defaults use representative public figures (documented on each field)
and should be treated as illustrative, not authoritative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

#: Complexity model per algorithm's *classical* baseline (what we extrapolate).
#: "exponential": cost ~ base^n (exact combinatorial / diagonalization / dense solve)
#: "quadratic_precision": classical cost ~ 1/eps^2 vs quantum ~ 1/eps (Monte Carlo)
CLASSICAL_COMPLEXITY: dict[str, str] = {
    "maxcut-qaoa": "exponential",
    "vqe-ising": "exponential",
    "gbs-dense-subgraph": "exponential",
    "cfd-vqls": "exponential",
    "quantum-monte-carlo": "quadratic_precision",
}


@dataclass
class ProjectionAssumptions:
    # --- complexity ---
    #: Effective branching factor of the classical cost curve, cost ~ base^n.
    classical_base: float = 2.0
    #: Hybrid cost per instance grows polynomially in n: cost ~ n^degree.
    hybrid_poly_degree: float = 3.0
    #: For Monte Carlo: classical samples ~ 1/eps^2, quantum oracle calls ~ 1/eps.
    #: --- energy (representative HPC figures) ---
    hpc_node_power_kw: float = 6.0  # a dense GPU/CPU HPC node under load (~6 kW)
    qpu_power_kw: float = 25.0  # a cryogenic/photonic QPU system incl. support plant
    energy_cost_per_kwh: float = 0.15  # USD/kWh industrial electricity
    # --- money ---
    hpc_node_cost_per_hour: float = 3.0  # USD/node-hour (HPC/cloud)
    qpu_cost_per_hour: float = 300.0  # USD/hour of QPU access (illustrative)
    value_per_solution_usd: float = 500.0  # business value of one solved instance
    # --- projection window ---
    base_problem_size: int = 8  # size at which this run was measured
    target_problem_size: int = 40  # scale we project toward
    num_points: int = 24


def _classical_units(sizes: np.ndarray, base_size: int, complexity: str, assumptions: ProjectionAssumptions) -> np.ndarray:
    """Relative classical work vs the base size (dimensionless, >=1 at base)."""
    if complexity == "quadratic_precision":
        # 'size' here is the number of accuracy digits d; work ~ 100^d.
        return np.power(100.0, sizes - base_size)
    return np.power(assumptions.classical_base, sizes - base_size)


def _hybrid_units(sizes: np.ndarray, base_size: int, complexity: str, assumptions: ProjectionAssumptions) -> np.ndarray:
    """Relative hybrid work vs the base size (dimensionless, >=1 at base)."""
    if complexity == "quadratic_precision":
        # quantum amplitude estimation ~ 10^d for d digits.
        return np.power(10.0, sizes - base_size)
    safe = np.maximum(sizes, 1)
    return np.power(safe / float(max(base_size, 1)), assumptions.hybrid_poly_degree)


def project(
    algorithm_id: str,
    measured: dict[str, Any],
    assumptions: ProjectionAssumptions | None = None,
) -> dict[str, Any]:
    """Build efficiency/power/cost/profit projections from measured times.

    ``measured`` must contain ``classical_seconds``, ``hybrid_seconds`` and
    ``problem_size`` for this run.
    """
    a = assumptions or ProjectionAssumptions()
    complexity = CLASSICAL_COMPLEXITY.get(algorithm_id, "exponential")

    if complexity == "quadratic_precision":
        # The scaling axis is accuracy digits, not qubits/nodes: anchor on a
        # modest base precision and project toward high precision. (Reaching
        # many digits by pure Monte Carlo is the classic infeasibility.)
        base_size = 2
        a.base_problem_size = base_size
        a.target_problem_size = 8
    else:
        base_size = int(measured.get("problem_size") or a.base_problem_size)
        a.base_problem_size = base_size

    classical_t0 = max(float(measured["classical_seconds"]), 1e-6)
    hybrid_t0 = max(float(measured["hybrid_seconds"]), 1e-6)

    target = max(a.target_problem_size, base_size + 1)
    sizes = np.unique(np.linspace(base_size, target, a.num_points).astype(int))

    classical_time = classical_t0 * _classical_units(sizes, base_size, complexity, a)
    hybrid_time = hybrid_t0 * _hybrid_units(sizes, base_size, complexity, a)

    # energy (kWh) = power (kW) * time (hours)
    classical_energy = a.hpc_node_power_kw * (classical_time / 3600.0)
    hybrid_energy = a.qpu_power_kw * (hybrid_time / 3600.0)

    # cost (USD) = rate (USD/hour) * time (hours)
    classical_cost = a.hpc_node_cost_per_hour * (classical_time / 3600.0)
    hybrid_cost = a.qpu_cost_per_hour * (hybrid_time / 3600.0)

    curve = [
        {
            "size": int(n),
            "classical_time": float(ct),
            "hybrid_time": float(ht),
            "classical_energy": float(ce),
            "hybrid_energy": float(he),
            "classical_cost": float(cc),
            "hybrid_cost": float(hc),
            "speedup": float(ct / ht) if ht > 0 else float("inf"),
        }
        for n, ct, ht, ce, he, cc, hc in zip(
            sizes, classical_time, hybrid_time, classical_energy, hybrid_energy, classical_cost, hybrid_cost
        )
    ]

    crossover = next((int(p["size"]) for p in curve if p["hybrid_time"] < p["classical_time"]), None)

    last = curve[-1]
    time_speedup = last["speedup"]
    energy_saved = last["classical_energy"] - last["hybrid_energy"]
    cost_saved = last["classical_cost"] - last["hybrid_cost"]
    # simple profit model: value delivered per instance minus the compute cost.
    hybrid_profit = a.value_per_solution_usd - last["hybrid_cost"]
    classical_profit = a.value_per_solution_usd - last["classical_cost"]
    roi = (cost_saved / last["hybrid_cost"]) if last["hybrid_cost"] > 0 else float("inf")

    return {
        "is_projection": True,
        "disclaimer": (
            "PROJECTION (model, not measured). Anchored on this run's measured wall times and "
            "extrapolated with the stated complexity and cost assumptions. Illustrative only."
        ),
        "complexity_model": complexity,
        "base_size": base_size,
        "target_size": int(target),
        "size_label": "accuracy digits" if complexity == "quadratic_precision" else "problem size (qubits/nodes)",
        "assumptions": asdict(a),
        "curve": curve,
        "crossover_size": crossover,
        "headline": {
            "target_size": int(target),
            "time_speedup": time_speedup,
            "energy_saved_kwh": float(energy_saved),
            "cost_saved_usd": float(cost_saved),
            "roi_multiple": float(roi),
            "hybrid_profit_usd": float(hybrid_profit),
            "classical_profit_usd": float(classical_profit),
        },
    }
