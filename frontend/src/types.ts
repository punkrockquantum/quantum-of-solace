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
  bitstring?: string;
  circuit_evaluations?: number;
  evaluations?: number;
  scaling_note?: string;
  simulated?: boolean;
  history?: { iteration: number; best: number }[];
}

export interface BenchmarkResult {
  algorithm: string;
  problem: Record<string, unknown>;
  optimal: { cut?: number; energy?: number; bitstring?: string; source: string };
  paths: { classical: PathResult; quantum: PathResult; hybrid: PathResult };
  quality_label: string;
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
