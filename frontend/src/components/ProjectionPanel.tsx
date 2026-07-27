import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Projection } from "../types";

function money(value: number): string {
  const abs = Math.abs(value);
  if (abs > 0 && abs < 0.01) return `$${value.toExponential(2)}`;
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(value / 1e3).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

function compact(value: number): string {
  if (!isFinite(value)) return "∞";
  const abs = Math.abs(value);
  if (abs >= 1e6 || (abs > 0 && abs < 1e-2)) return value.toExponential(1);
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}k`;
  return value.toFixed(1);
}

const CHARTS: {
  title: string;
  caption: string;
  classicalKey: "classical_time" | "classical_energy" | "classical_cost";
  hybridKey: "hybrid_time" | "hybrid_energy" | "hybrid_cost";
  unit: string;
}[] = [
  { title: "Time to solution", caption: "Wall-clock seconds per instance", classicalKey: "classical_time", hybridKey: "hybrid_time", unit: "s" },
  { title: "Energy per solution", caption: "kWh per instance", classicalKey: "classical_energy", hybridKey: "hybrid_energy", unit: "kWh" },
  { title: "Cost per solution", caption: "USD per instance", classicalKey: "classical_cost", hybridKey: "hybrid_cost", unit: "$" },
];

export default function ProjectionPanel({ projection }: { projection: Projection }) {
  const h = projection.headline;
  const infra = projection.infrastructure;
  const profile = infra.profile;
  const memory = infra.memory;
  const chartData = projection.curve.map((p) => ({
    size: p.size,
    classical_time: p.classical_time,
    hybrid_time: p.hybrid_time,
    classical_energy: p.classical_energy,
    hybrid_energy: p.hybrid_energy,
    classical_cost: p.classical_cost,
    hybrid_cost: p.hybrid_cost,
  }));

  return (
    <section className="panel">
      <div className="projection-header">
        <h2 style={{ margin: 0 }}>Advantage at scale</h2>
        <span className="projected-tag">Projected · model</span>
      </div>
      <p className="projection-disclaimer">{projection.disclaimer}</p>

      <div className="headline-grid">
        <Headline label={`Speed-up at ${h.target_size} ${projection.size_label}`} value={`${compact(h.time_speedup)}x`} good />
        <Headline label="Energy saved / instance" value={`${compact(h.energy_saved_kwh)} kWh`} good />
        <Headline label="Cost saved / instance" value={money(h.cost_saved_usd)} good />
        <Headline label="Return on compute (ROI)" value={`${compact(h.roi_multiple)}x`} good />
      </div>

      <div className="gb300-summary">
        <div className="projection-header">
          <h3 style={{ margin: 0 }}>{profile.name} rack-scale model</h3>
          <span className="projected-tag">SIMULATION · MODEL</span>
        </div>
        <p className="projection-disclaimer">{infra.compute_basis}</p>
        <div className="headline-grid gb300">
          <Headline label="Modeled compute wall time" value={formatSeconds(infra.compute_wall_time_seconds)} />
          <Headline
            label={`Internal latency (target ≤${profile.cluster_latency_target_ms} ms)`}
            value={`${compact(infra.internal_latency.value_ms)} ms · ${infra.internal_latency.meets_target ? "PASS" : "FAIL"}`}
            good={infra.internal_latency.meets_target}
          />
          <Headline
            label={`End-to-end latency (target ≤${profile.end_to_end_latency_target_ms} ms)`}
            value={`${compact(infra.end_to_end_latency.value_ms)} ms · ${infra.end_to_end_latency.meets_target ? "PASS" : "FAIL"}`}
            good={infra.end_to_end_latency.meets_target}
          />
          <Headline
            label="Statevector memory headroom"
            value={memory.headroom_tb === null ? "N/A for this axis" : `${compact(memory.headroom_tb)} TB · ${memory.fits ? "FITS" : "EXCEEDS"}`}
            good={memory.fits === true}
          />
          <Headline label="Rack energy / solution" value={`${compact(infra.energy_kwh)} kWh`} />
          <Headline label="Illustrative rack cost / solution" value={money(infra.illustrative_compute_cost_usd)} />
          <Headline label="Value / modeled cost" value={`${compact(h.gb300_value_per_cost)}x`} />
          <Headline label="Rack configuration" value={`${profile.gpu_count} GPUs · ${profile.gpu_memory_tb} TB HBM3e`} />
        </div>
        <p className="projection-disclaimer">
          {infra.kv_cache_note} Network round-trip ({profile.network_round_trip_ms} ms) is modeled separately from
          compute and {profile.intra_cluster_overhead_ms} ms in-cluster overhead.
        </p>
      </div>

      {projection.crossover_size !== null && (
        <div className="crossover-note">
          Break-even at <strong>{projection.crossover_size} {projection.size_label}</strong>: below this the classical
          method is cheaper; above it the hybrid workflow pulls ahead, and the gap widens with a{" "}
          {projection.complexity_model === "quadratic_precision" ? "quadratic" : "super-polynomial"} curve.
        </div>
      )}

      <div className="projection-charts">
        {CHARTS.map((chart) => (
          <div key={chart.title} className="projection-chart">
            <div className="projection-chart-title">{chart.title}</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData} margin={{ top: 6, right: 12, bottom: 2, left: 0 }}>
                <CartesianGrid stroke="#232a38" strokeDasharray="3 3" />
                <XAxis dataKey="size" stroke="#8b94a7" fontSize={10} />
                <YAxis stroke="#8b94a7" fontSize={10} scale="log" domain={["auto", "auto"]} tickFormatter={compact} width={44} />
                <Tooltip
                  contentStyle={{ background: "#171c27", border: "1px solid #232a38", borderRadius: 8, fontSize: 12 }}
                  labelFormatter={(l) => `${projection.size_label}: ${l}`}
                  formatter={(v: number) => compact(v) + " " + chart.unit}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey={chart.classicalKey} name="classical" stroke="var(--classical)" dot={false} strokeWidth={2} isAnimationActive={false} />
                <Line type="monotone" dataKey={chart.hybridKey} name="hybrid" stroke="var(--hybrid)" dot={false} strokeWidth={2} isAnimationActive={false} />
                {projection.crossover_size !== null && (
                  <ReferenceLine x={projection.crossover_size} stroke="#fbbf24" strokeDasharray="4 4" />
                )}
              </LineChart>
            </ResponsiveContainer>
            <div className="chart-caption">{chart.caption} (log scale)</div>
          </div>
        ))}
      </div>

      <details className="assumptions">
        <summary>Model assumptions (adjust in the backend)</summary>
        <div className="assumptions-grid">
          <Assumption label="Classical scaling" value={projection.complexity_model === "quadratic_precision" ? "~1/ε² (samples)" : `~${projection.assumptions.classical_base}^n`} />
          <Assumption label="Hybrid scaling" value={projection.complexity_model === "quadratic_precision" ? "~1/ε (oracle calls)" : `~n^${projection.assumptions.hybrid_poly_degree}`} />
          <Assumption label="Classical node power" value={`${projection.assumptions.hpc_node_power_kw} kW`} />
          <Assumption label="GB300 rack power" value={`${profile.rack_power_kw} kW`} />
          <Assumption label="GPU HBM3e / usable" value={`${profile.gpu_memory_tb} / ${memory.usable_gpu_memory_tb} TB`} />
          <Assumption label="NVLink aggregate bandwidth" value={`${profile.nvlink_bandwidth_tbps} TB/s`} />
          <Assumption label="Energy price" value={`$${projection.assumptions.energy_cost_per_kwh}/kWh`} />
          <Assumption label="Classical node cost" value={`$${projection.assumptions.hpc_node_cost_per_hour}/node-hr`} />
          <Assumption label="GB300 rack cost (illustrative)" value={`$${profile.illustrative_rack_cost_per_hour_usd}/rack-hr`} />
          <Assumption label="Value / solution" value={money(projection.assumptions.value_per_solution_usd)} />
        </div>
        <p>
          NVIDIA-sourced hardware facts: {profile.gpu_count} Blackwell Ultra GPUs, {profile.grace_cpu_count} Grace
          CPUs, {profile.gpu_memory_tb} TB GPU memory, {profile.total_fast_memory_tb} TB total fast memory,{" "}
          {profile.nvlink_bandwidth_tbps} TB/s NVLink bandwidth, and approximately {profile.rack_power_kw} kW rack
          power. Latency targets, utilization, energy price, and rack-hour cost are user/model assumptions.
        </p>
        <p>
          Sources:{" "}
          {infra.sources.map((source, index) => (
            <span key={source.url}>
              {index > 0 && " · "}
              <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
            </span>
          ))}
        </p>
      </details>
    </section>
  );
}

function formatSeconds(seconds: number): string {
  if (seconds < 0.001) return `${compact(seconds * 1e6)} µs`;
  if (seconds < 1) return `${compact(seconds * 1e3)} ms`;
  return `${compact(seconds)} s`;
}

function Headline({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="headline-card">
      <div className={"headline-value" + (good ? " good" : "")}>{value}</div>
      <div className="headline-label">{label}</div>
    </div>
  );
}

function Assumption({ label, value }: { label: string; value: string }) {
  return (
    <div className="assumption">
      <span className="k">{label}</span>
      <span className="v">{value}</span>
    </div>
  );
}
