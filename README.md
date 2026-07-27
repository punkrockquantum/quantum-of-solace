# Quantum of Solace

**Hybrid quantum-classical workflow orchestration — simulators, real hardware, and cloud platforms behind one simple interface.**

Quantum of Solace lets you run hybrid quantum algorithms and see — with honest, measured numbers — how a hybrid classical/quantum workflow compares against pure-classical and pure-quantum approaches. No quantum expertise required: pick a problem, pick a backend, press Run.

## What it does

- **Orchestrates hybrid workflows**: a classical optimizer (HPC-friendly, NumPy/SciPy) drives parameterized quantum kernels dispatched to any registered backend.
- **Unified backend framework**: one `QuantumBackend` interface covering
  - **Local simulation** — a built-in NumPy statevector simulator (the demo workhorse)
  - **GPU-accelerated simulation** — [NVIDIA CUDA-Q](https://developer.nvidia.com/cuda-q) adapter (activates automatically on Linux hosts with `cudaq` installed; the orchestrator is written against the generic interface, so switching to CUDA-Q in the lab is a config change)
  - **Control hardware** — RFSoC via [QICK](https://github.com/openquantumhardware/qick) (AMD Xilinx ZCU111 / ZCU216), Quantum Machines (QUA/OPX), QBLOX Cluster
  - **Quantum platforms** — ORCA Computing PT-2 (photonic), IQM (superconducting), Atom Computing and QuEra (neutral atoms)
  - **Cloud services** — AWS Braket, Strangeworks
- **Honest comparison engine**: runs the same problem classically (exact where tractable), pure-quantum (sampling, no classical optimization), and hybrid — and reports *measured* solution quality and wall time. Every number in the UI comes from an actual computation. Results produced in simulation are always labeled as simulation.
- **Advantage-at-scale projection**: a transparent model that takes this run's *measured local* wall times and extrapolates the efficiency, energy, cost, and value difference as the problem grows. It includes an adjustable NVIDIA GB300 NVL72 rack-scale profile and is clearly labeled as a simulation/model, never as a hardware measurement.
- **Simple UI**: a local React dashboard designed for people with zero quantum background.

## Algorithms

Each algorithm runs the same problem three ways — pure classical (exact/proven baseline), pure quantum (no classical optimization), and hybrid (classical optimizer driving quantum circuits) — and every reported number is measured on that run.

| Algorithm | Domain | Classical baseline | Quantum / hybrid method |
|---|---|---|---|
| **Max-Cut (QAOA)** | logistics, chip design, portfolio clustering | exact brute force over all partitions | QAOA + COBYLA |
| **Ground-state energy (VQE)** | chemistry, materials, quantum magnetism | exact diagonalization | hardware-efficient VQE + COBYLA |
| **Dense communities (GBS)** | life sciences (protein complexes, molecular motifs) | exact densest-subgraph search | Gaussian Boson Sampling + greedy local search |
| **Expectation estimation (Quantum Monte Carlo)** | finance, physics integrals | classical Monte Carlo (error ~1/√N) | Maximum-Likelihood Amplitude Estimation (error ~1/N) |
| **Fluid dynamics (VQLS)** | CFD, any large linear system | exact dense linear solve | Variational Quantum Linear Solver + COBYLA |

The scientific basis for each (hafnian-based GBS distributions, amplitude estimation, VQLS cost functions) is documented in the module docstrings under `backend/qsolace/algorithms/`. Feed in new algorithms by adding a module with a `run_comparison` function and a descriptor in `algorithms/__init__.py`; the API and UI pick them up automatically.

## Measured vs projected — the integrity line

At the small sizes that run instantly in the browser, an exact classical method is cheap and often wins outright. That is reported honestly. The *advantage* story lives in the clearly-labeled scaling **projection**: it anchors on measured local exact-simulator wall times and extrapolates using stated complexity assumptions. No GB300 acceleration factor is invented or claimed. The model applies rack power, memory, latency, energy, and configurable economic assumptions to that projected compute time. Measured results and GB300 modeled results remain separate in both the API and UI.

### NVIDIA GB300 NVL72 model

The named profile represents one liquid-cooled rack-scale system, not a generic HPC node. NVIDIA-sourced defaults are:

- 72 NVIDIA Blackwell Ultra GPUs and 36 NVIDIA Grace CPUs
- 20 TB aggregate GPU HBM3e, 37 TB total fast memory, and up to 576 TB/s aggregate GPU-memory bandwidth
- 130 TB/s aggregate NVLink bandwidth
- approximately 120 kW rack power

Sources: [NVIDIA GB300 NVL72 product page](https://www.nvidia.com/en-us/data-center/gb300-nvl72/) and [NVIDIA DGX GB Rack Scale Systems User Guide — Hardware](https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html).

The following are **user/model assumptions, not NVIDIA specifications or guarantees**: 80% usable GPU-memory fraction, 1.2x statevector allocation overhead, 0.5 ms intra-cluster overhead, 12 ms network round trip, the requested ≤5 ms internal and ≤20 ms end-to-end latency targets, $0.15/kWh electricity, $100/rack-hour illustrative compute cost, and $500 value per solution. NVIDIA does not publish a universal GB300 purchase or cloud price, so the rack-hour input is deliberately adjustable and must not be treated as a quote.

Quantum statevector memory is modeled as 16 bytes per complex128 amplitude plus configurable overhead. A 40-qubit bare statevector is about 17.6 decimal TB; with the default 1.2x overhead it exceeds the profile's 16 TB usable-memory assumption. The UI reports this explicitly rather than implying that all projected workloads fit. **KV cache is an AI-inference resource, not the quantum statevector**; it is mentioned only as an optional co-hosted AI orchestration workload that would further reduce available GPU memory.

Latency is decomposed into projected compute wall time, intra-cluster overhead, and network round trip. A workload receives PASS only when its modeled value actually meets the target; the model never forces algorithm compute below 5 ms.

Outcome badges are also independent: **Highest Performance** maximizes measured solution quality (measured wall time breaks ties), while **Optimal Value** maximizes `70% × normalized measured quality + 30% × inverse projected GB300 rack compute cost`. One path can legitimately win both when the data supports it.

## Quick start

Requirements: Python ≥ 3.10, Node ≥ 18.

```bash
make install   # create backend venv + install, npm install frontend
make dev       # backend on http://localhost:8000, UI on http://localhost:5173
```

Then open http://localhost:5173, pick a problem (e.g. Max-Cut), pick a backend, and press **Run comparison**.

Run the test suite:

```bash
make test
```

## Architecture

```
frontend/   React + TypeScript + Vite dashboard (REST + Server-Sent Events)
backend/    Python package `qsolace` (FastAPI)
  qsolace/core/          circuit IR, jobs, results, QuantumBackend interface, registry
  qsolace/backends/      local simulator, CUDA-Q adapter
    control/             QICK (RFSoC), Quantum Machines, QBLOX drivers
    platforms/           ORCA PT-Series, IQM, Atom Computing, QuEra
    cloud/               AWS Braket, Strangeworks
  qsolace/orchestrator/  hybrid workflow engine, job queue, live progress events
  qsolace/algorithms/    Max-Cut (QAOA), VQE (Ising), GBS dense subgraph,
                         Quantum Monte Carlo (amplitude estimation), CFD (VQLS)
  qsolace/comparison/    classical vs quantum vs hybrid benchmark engine
                         + advantage-at-scale projection model
```

### Backend modes

Each backend reports one of four modes so nothing is ever silently faked:

| Mode | Meaning |
|---|---|
| `connected` | Real device/service reachable; results come from actual hardware/cloud |
| `simulated` | Driver present but no hardware attached; execution is delegated to the local simulator and labeled as such |
| `not_configured` | Cloud credentials missing; the UI shows setup instructions |
| `unavailable` | Required SDK not installed on this host (e.g. CUDA-Q on macOS) |

### Connecting real hardware

Hardware and cloud connections are configured entirely through environment variables — see [.env.example](.env.example). No credentials are ever stored in the repository. In a lab deployment, point the control adapters (QICK / Quantum Machines / QBLOX) at your instruments' IP addresses and they switch from `simulated` to `connected`.

## Scientific integrity

Quantum of Solace never fabricates results:

- Quantum circuit results come from exact statevector simulation (or real hardware when connected).
- Classical baselines are exact (brute force / dense diagonalization) on the small problem sizes used in the demo, so approximation ratios are ground-truth-verified.
- Wall times are measured, not estimated.
- Anything computed in simulation is labeled *simulation* in the API and the UI.

## License

MIT — see [LICENSE](LICENSE).
