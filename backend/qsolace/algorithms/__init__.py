"""Algorithm catalog.

Each algorithm module implements three execution paths over the same
problem instance:

- ``classical``  exact (or best-known classical) solution with measured time
- ``quantum``    quantum sampling without any classical optimization
- ``hybrid``     classical optimizer driving parameterized quantum circuits

New algorithms are added by writing a module with a ``run_comparison``
function and registering a descriptor here; the API and UI pick them up
automatically.
"""

from __future__ import annotations

from typing import Any, Callable

from qsolace.core.backend import QuantumBackend

ProgressCallback = Callable[[dict[str, Any]], None]

#: UI-facing descriptors: parameter schemas drive the frontend form.
ALGORITHMS: list[dict[str, Any]] = [
    {
        "id": "maxcut-qaoa",
        "name": "Max-Cut (QAOA)",
        "summary": "Split a network into two groups so the most connections are cut. Used in logistics, chip design and portfolio risk clustering.",
        "params": [
            {"id": "num_nodes", "label": "Problem size (nodes)", "type": "int", "default": 8, "min": 4, "max": 16},
            {"id": "edge_probability", "label": "Connection density", "type": "float", "default": 0.5, "min": 0.2, "max": 1.0},
            {"id": "layers", "label": "QAOA depth (p)", "type": "int", "default": 2, "min": 1, "max": 4},
            {"id": "shots", "label": "Measurement shots", "type": "int", "default": 2048, "min": 256, "max": 8192},
            {"id": "max_iterations", "label": "Optimizer iterations", "type": "int", "default": 80, "min": 20, "max": 300},
            {"id": "seed", "label": "Random seed", "type": "int", "default": 7, "min": 0, "max": 999999},
        ],
    },
    {
        "id": "vqe-ising",
        "name": "Ground-state energy (VQE, Ising model)",
        "summary": "Find the lowest energy of a quantum magnet. The same workflow powers molecular chemistry and materials simulation.",
        "params": [
            {"id": "num_qubits", "label": "Problem size (spins)", "type": "int", "default": 4, "min": 2, "max": 10},
            {"id": "layers", "label": "Ansatz depth", "type": "int", "default": 2, "min": 1, "max": 4},
            {"id": "coupling_j", "label": "Coupling strength J", "type": "float", "default": 1.0, "min": 0.1, "max": 2.0},
            {"id": "field_h", "label": "Transverse field h", "type": "float", "default": 1.0, "min": 0.0, "max": 2.0},
            {"id": "shots", "label": "Measurement shots", "type": "int", "default": 2048, "min": 256, "max": 8192},
            {"id": "max_iterations", "label": "Optimizer iterations", "type": "int", "default": 150, "min": 30, "max": 500},
            {"id": "seed", "label": "Random seed", "type": "int", "default": 7, "min": 0, "max": 999999},
        ],
    },
]


def run_comparison(
    algorithm_id: str,
    params: dict[str, Any],
    backend: QuantumBackend,
    progress: ProgressCallback,
) -> dict[str, Any]:
    if algorithm_id == "maxcut-qaoa":
        from qsolace.algorithms import maxcut_qaoa

        return maxcut_qaoa.run_comparison(params, backend, progress)
    if algorithm_id == "vqe-ising":
        from qsolace.algorithms import vqe_ising

        return vqe_ising.run_comparison(params, backend, progress)
    raise KeyError(f"unknown algorithm '{algorithm_id}'")
