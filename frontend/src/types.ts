export type BackendMode = "connected" | "simulated" | "not_configured" | "unavailable";

export interface BackendInfo {
  id: string;
  name: string;
  vendor: string;
  kind: "simulator" | "control_hardware" | "platform" | "cloud";
  mode: BackendMode;
  description: string;
  max_qubits: number;
  mode_detail: string;
}

export interface AlgorithmParam {
  id: string;
  label: string;
  type: "int" | "float";
  default: number;
  min: number;
  max: number;
}

export interface Algorithm {
  id: string;
  name: string;
  summary: string;
  params: AlgorithmParam[];
}

export interface ProgressEvent {
  type: "status" | "progress";
  phase?: string;
  message?: string;
  iteration?: number;
  value?: number;
  best?: number;
  target?: number;
  status?: string;
  error?: string;
  ts?: number;
}

export interface PathResult {
  method: string;
  elapsed_seconds: number;
  approximation_ratio?: number;
  expected_approximation_ratio?: number;
  quality?: number;
  cut?: number;
  expected_cut?: number;
  energy?: number;
  energy_error?: number;
  estimate?: number;
  error?: number;
  fidelity?: number;
  residual?: number;
  density?: number;
  oracle_calls?: number;
  bitstring?: string;
  circuit_evaluations?: number;
  evaluations?: number;
  scaling_note?: string;
  simulated?: boolean;
  history?: { iteration: number; best: number }[];
}

export interface ProjectionCurvePoint {
  size: number;
  classical_time: number;
  hybrid_time: number;
  classical_energy: number;
  hybrid_energy: number;
  classical_cost: number;
  hybrid_cost: number;
  speedup: number;
}

export interface Projection {
  is_projection: true;
  disclaimer: string;
  complexity_model: string;
  base_size: number;
  target_size: number;
  size_label: string;
  assumptions: Record<string, number>;
  infrastructure: {
    profile: {
      name: string;
      gpu_count: number;
      grace_cpu_count: number;
      gpu_memory_tb: number;
      total_fast_memory_tb: number;
      nvlink_bandwidth_tbps: number;
      gpu_memory_bandwidth_tbps: number;
      rack_power_kw: number;
      usable_gpu_memory_fraction: number;
      intra_cluster_overhead_ms: number;
      network_round_trip_ms: number;
      cluster_latency_target_ms: number;
      end_to_end_latency_target_ms: number;
      illustrative_rack_cost_per_hour_usd: number;
    };
    classification: string;
    compute_basis: string;
    compute_wall_time_seconds: number;
    internal_latency: { value_ms: number; target_ms: number; meets_target: boolean };
    end_to_end_latency: { value_ms: number; target_ms: number; meets_target: boolean };
    energy_kwh: number;
    illustrative_compute_cost_usd: number;
    illustrative_energy_cost_usd: number;
    memory: {
      model: string;
      required_gpu_memory_tb: number | null;
      usable_gpu_memory_tb: number;
      headroom_tb: number | null;
      fits: boolean | null;
    };
    kv_cache_note: string;
    sources: { title: string; url: string }[];
  };
  curve: ProjectionCurvePoint[];
  crossover_size: number | null;
  headline: {
    target_size: number;
    time_speedup: number;
    energy_saved_kwh: number;
    cost_saved_usd: number;
    roi_multiple: number;
    hybrid_profit_usd: number;
    classical_profit_usd: number;
    gb300_value_per_cost: number;
  };
}

export interface BenchmarkResult {
  algorithm: string;
  problem: Record<string, unknown>;
  optimal: { cut?: number; energy?: number; density?: number; estimate?: number; fidelity?: number; source: string };
  paths: { classical: PathResult; quantum: PathResult; hybrid: PathResult };
  quality_label: string;
  projection: Projection;
  outcomes: {
    highest_performance: "classical" | "quantum" | "hybrid";
    optimal_value: "classical" | "quantum" | "hybrid";
    value_scores: Record<"classical" | "quantum" | "hybrid", number>;
    projected_cost_usd: Record<"classical" | "quantum" | "hybrid", number>;
    definition: string;
  };
  provenance: {
    backend_id: string;
    backend_name: string;
    backend_mode: string;
    simulated: boolean;
    statement: string;
  };
}

export interface JobInfo {
  id: string;
  algorithm_id: string;
  backend_id: string;
  status: "queued" | "running" | "completed" | "failed";
  error: string | null;
  result?: BenchmarkResult | null;
}
