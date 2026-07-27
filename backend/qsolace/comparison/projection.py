"""Scaling and GB300 NVL72 infrastructure projections.

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

Hardware facts in :class:`InfrastructureProfile` come from NVIDIA's product
page and rack-scale user guide. Latency, utilization, and economic inputs are
explicitly configurable assumptions; they are not NVIDIA specifications.

Sources:
* NVIDIA, "NVIDIA GB300 NVL72":
  https://www.nvidia.com/en-us/data-center/gb300-nvl72/
* NVIDIA, "DGX GB Rack Scale Systems User Guide — Hardware":
  https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
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

NVIDIA_GB300_PRODUCT_URL = "https://www.nvidia.com/en-us/data-center/gb300-nvl72/"
NVIDIA_GB_RACK_GUIDE_URL = "https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html"


@dataclass(frozen=True)
class InfrastructureProfile:
    """Named rack-scale infrastructure facts and adjustable model inputs."""

    name: str = "NVIDIA GB300 NVL72"
    # NVIDIA-published hardware specifications.
    gpu_count: int = 72
    grace_cpu_count: int = 36
    gpu_memory_tb: float = 20.0
    total_fast_memory_tb: float = 37.0
    nvlink_bandwidth_tbps: float = 130.0
    gpu_memory_bandwidth_tbps: float = 576.0
    rack_power_kw: float = 120.0
    # User/model assumptions, not NVIDIA guarantees or prices.
    usable_gpu_memory_fraction: float = 0.80
    statevector_overhead_factor: float = 1.20
    intra_cluster_overhead_ms: float = 0.50
    network_round_trip_ms: float = 12.0
    cluster_latency_target_ms: float = 5.0
    end_to_end_latency_target_ms: float = 20.0
    illustrative_rack_cost_per_hour_usd: float = 100.0


@dataclass
class ProjectionAssumptions:
    # --- complexity ---
    #: Effective branching factor of the classical cost curve, cost ~ base^n.
    classical_base: float = 2.0
    #: Hybrid cost per instance grows polynomially in n: cost ~ n^degree.
    hybrid_poly_degree: float = 3.0
    #: For Monte Carlo: classical samples ~ 1/eps^2, quantum oracle calls ~ 1/eps.
    #: --- energy (representative non-GB300 classical baseline) ---
    hpc_node_power_kw: float = 6.0  # a dense GPU/CPU HPC node under load (~6 kW)
    energy_cost_per_kwh: float = 0.15  # USD/kWh industrial electricity
    # --- money ---
    hpc_node_cost_per_hour: float = 3.0  # USD/node-hour (HPC/cloud)
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


def statevector_memory_tb(num_qubits: int, overhead_factor: float = 1.0) -> float:
    """Return decimal TB for a complex128 statevector plus modelled overhead."""
    if num_qubits < 0:
        raise ValueError("num_qubits must be non-negative")
    return math.ldexp(16.0 * overhead_factor, num_qubits) / 1e12


def _latency_status(value_ms: float, target_ms: float) -> dict[str, Any]:
    return {"value_ms": value_ms, "target_ms": target_ms, "meets_target": value_ms <= target_ms}


def _gb300_projection(
    algorithm_id: str,
    target_size: int,
    compute_seconds: float,
    energy_cost_per_kwh: float,
    profile: InfrastructureProfile,
) -> dict[str, Any]:
    """Apply rack power, memory, latency, and cost assumptions to modelled work."""
    compute_ms = max(compute_seconds, 0.0) * 1000.0
    internal_ms = compute_ms + profile.intra_cluster_overhead_ms
    end_to_end_ms = internal_ms + profile.network_round_trip_ms
    hours = compute_seconds / 3600.0
    energy_kwh = profile.rack_power_kw * hours
    compute_cost = profile.illustrative_rack_cost_per_hour_usd * hours
    energy_cost = energy_kwh * energy_cost_per_kwh

    # Only these algorithms map the projection axis directly to statevector
    # qubits. GBS modes and QMC accuracy digits require different memory models.
    memory_model_applies = algorithm_id in {"maxcut-qaoa", "vqe-ising", "cfd-vqls"}
    required_tb = (
        statevector_memory_tb(target_size, profile.statevector_overhead_factor)
        if memory_model_applies
        else None
    )
    usable_tb = profile.gpu_memory_tb * profile.usable_gpu_memory_fraction
    headroom_tb = usable_tb - required_tb if required_tb is not None else None

    return {
        "profile": asdict(profile),
        "classification": "SIMULATION/MODEL — not executed on GB300 hardware",
        "compute_basis": (
            "Measured local exact-simulator wall time scaled by the algorithm model; "
            "no unverified GB300 speed-up factor is applied."
        ),
        "compute_wall_time_seconds": compute_seconds,
        "internal_latency": _latency_status(internal_ms, profile.cluster_latency_target_ms),
        "end_to_end_latency": _latency_status(end_to_end_ms, profile.end_to_end_latency_target_ms),
        "energy_kwh": energy_kwh,
        "illustrative_compute_cost_usd": compute_cost,
        "illustrative_energy_cost_usd": energy_cost,
        "memory": {
            "model": (
                "complex128 statevector (16 bytes/amplitude) with configurable overhead; "
                "KV cache is not quantum-state memory"
            ),
            "required_gpu_memory_tb": required_tb,
            "usable_gpu_memory_tb": usable_tb,
            "headroom_tb": headroom_tb,
            "fits": headroom_tb >= 0.0 if headroom_tb is not None else None,
        },
        "kv_cache_note": (
            "KV cache applies only to an optional co-hosted AI orchestration/inference workload. "
            "Quantum statevector simulation consumes GPU memory independently."
        ),
        "sources": [
            {"title": "NVIDIA GB300 NVL72", "url": NVIDIA_GB300_PRODUCT_URL},
            {
                "title": "DGX GB Rack Scale Systems User Guide — Hardware",
                "url": NVIDIA_GB_RACK_GUIDE_URL,
            },
        ],
    }


def project(
    algorithm_id: str,
    measured: dict[str, Any],
    assumptions: ProjectionAssumptions | None = None,
    infrastructure: InfrastructureProfile | None = None,
) -> dict[str, Any]:
    """Build efficiency/power/cost/profit projections from measured times.

    ``measured`` must contain ``classical_seconds``, ``hybrid_seconds`` and
    ``problem_size`` for this run.
    """
    a = assumptions or ProjectionAssumptions()
    profile = infrastructure or InfrastructureProfile()
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
    hybrid_energy = profile.rack_power_kw * (hybrid_time / 3600.0)

    # cost (USD) = rate (USD/hour) * time (hours)
    classical_cost = a.hpc_node_cost_per_hour * (classical_time / 3600.0)
    hybrid_cost = profile.illustrative_rack_cost_per_hour_usd * (hybrid_time / 3600.0)

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
    gb300 = _gb300_projection(
        algorithm_id,
        int(target),
        float(last["hybrid_time"]),
        a.energy_cost_per_kwh,
        profile,
    )

    return {
        "is_projection": True,
        "disclaimer": (
            "PROJECTION — SIMULATION/MODEL (not run on GB300 hardware). Anchored on measured local exact-simulator "
            "wall times and extrapolated with stated scaling, latency, power, and cost assumptions."
        ),
        "complexity_model": complexity,
        "base_size": base_size,
        "target_size": int(target),
        "size_label": "accuracy digits" if complexity == "quadratic_precision" else "problem size (qubits/nodes)",
        "assumptions": asdict(a),
        "infrastructure": gb300,
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
            "gb300_value_per_cost": float(
                a.value_per_solution_usd / max(gb300["illustrative_compute_cost_usd"], 1e-12)
            ),
        },
    }
