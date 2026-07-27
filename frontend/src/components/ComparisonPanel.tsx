import type { BenchmarkResult, PathResult } from "../types";

const PATHS: { key: "classical" | "quantum" | "hybrid"; title: string; color: string }[] = [
  { key: "classical", title: "Pure classical", color: "var(--classical)" },
  { key: "quantum", title: "Pure quantum", color: "var(--quantum)" },
  { key: "hybrid", title: "Hybrid (quantum + classical)", color: "var(--hybrid)" },
];

function quality(path: PathResult): number {
  return path.approximation_ratio ?? path.quality ?? 0;
}

function formatSeconds(seconds: number): string {
  if (seconds < 0.001) return `${(seconds * 1e6).toFixed(0)} µs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)} ms`;
  return `${seconds.toFixed(2)} s`;
}

/** Algorithm-specific secondary metric shown on each card. */
function detailRows(algorithm: string, path: PathResult, result: BenchmarkResult): { k: string; v: string }[] {
  const rows: { k: string; v: string }[] = [];
  switch (algorithm) {
    case "maxcut-qaoa":
      if (path.cut !== undefined) rows.push({ k: "cut found", v: `${path.cut} / ${result.optimal.cut}` });
      break;
    case "vqe-ising":
      if (path.energy !== undefined) rows.push({ k: "energy", v: path.energy.toFixed(5) });
      if (result.optimal.energy !== undefined) rows.push({ k: "exact ground", v: result.optimal.energy.toFixed(5) });
      break;
    case "quantum-monte-carlo":
      if (path.estimate !== undefined) rows.push({ k: "estimate", v: path.estimate.toFixed(5) });
      if (path.error !== undefined) rows.push({ k: "abs. error", v: path.error.toExponential(2) });
      if (path.oracle_calls !== undefined) rows.push({ k: "oracle calls", v: path.oracle_calls.toLocaleString() });
      break;
    case "cfd-vqls":
      if (path.fidelity !== undefined) rows.push({ k: "fidelity", v: path.fidelity.toFixed(4) });
      if (path.residual !== undefined) rows.push({ k: "residual", v: path.residual.toExponential(2) });
      break;
    case "gbs-dense-subgraph":
      if (path.density !== undefined) rows.push({ k: "density", v: path.density.toFixed(3) });
      break;
  }
  const evals = path.circuit_evaluations ?? path.evaluations;
  if (evals !== undefined) rows.push({ k: "evaluations", v: evals.toLocaleString() });
  return rows;
}

function verdict(result: BenchmarkResult): string {
  const hybrid = quality(result.paths.hybrid);
  const quantum = quality(result.paths.quantum);
  const hybridPct = (hybrid * 100).toFixed(1);
  const parts = [
    `The hybrid workflow reached ${hybridPct}% on ${result.quality_label.toLowerCase()}, verified against the exact classical solution.`,
  ];
  if (hybrid > quantum + 0.005) {
    parts.push(
      `Adding the classical optimizer improved on pure quantum by ${((hybrid - quantum) * 100).toFixed(1)} percentage points.`,
    );
  }
  parts.push(
    "At this demo size the exact classical method is cheap and often wins outright - that is expected and honest. The advantage appears at scale: see the projection below.",
  );
  return parts.join(" ");
}

export default function ComparisonPanel({ result }: { result: BenchmarkResult }) {
  const qualities = PATHS.map(({ key }) => quality(result.paths[key]));
  const bestQuality = Math.max(...qualities);

  return (
    <div className="stack">
      <div className="verdict">{verdict(result)}</div>

      <div className="compare-grid">
        {PATHS.map(({ key, title, color }, i) => {
          const path = result.paths[key];
          const q = qualities[i];
          const winner = q >= bestQuality - 1e-9;
          return (
            <div key={key} className={"compare-card" + (winner ? " winner" : "")}>
              {winner && <span className="winner-badge">best quality</span>}
              <h3 style={{ color }}>{title}</h3>
              <div className="method">{path.method}</div>
              <div className="big-number" style={{ color }}>
                {(q * 100).toFixed(1)}%
              </div>
              <div className="quality-bar">
                <div style={{ width: `${Math.max(q * 100, 2)}%`, background: color }} />
              </div>
              <div className="metric-row">
                <span className="k">wall time (measured)</span>
                <span className="v">{formatSeconds(path.elapsed_seconds)}</span>
              </div>
              {detailRows(result.algorithm, path, result).map((row) => (
                <div className="metric-row" key={row.k}>
                  <span className="k">{row.k}</span>
                  <span className="v">{row.v}</span>
                </div>
              ))}
              {path.scaling_note && <div className="scaling-note">{path.scaling_note}</div>}
            </div>
          );
        })}
      </div>

      <div className="provenance">
        <span aria-hidden>ⓘ</span>
        <span>
          <strong>Where these numbers come from:</strong> {result.provenance.statement} Quality metric:{" "}
          {result.quality_label.toLowerCase()}.
        </span>
      </div>
    </div>
  );
}
