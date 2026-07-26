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

function verdict(result: BenchmarkResult): string {
  const hybrid = quality(result.paths.hybrid);
  const quantum = quality(result.paths.quantum);
  const isMaxcut = result.algorithm === "maxcut-qaoa";
  const unit = isMaxcut ? "of the mathematically optimal answer" : "of the exact ground-state quality";
  const hybridPct = (hybrid * 100).toFixed(1);
  const parts = [
    `The hybrid workflow reached ${hybridPct}% ${unit}, verified against the exact classical solution.`,
  ];
  if (hybrid > quantum) {
    parts.push(
      `Adding the classical optimizer improved on pure quantum sampling by ${((hybrid - quantum) * 100).toFixed(1)} percentage points.`,
    );
  }
  parts.push(
    "At this demo size the exact classical solve is instant - but its cost doubles with every extra variable, while the hybrid loop's per-iteration cost grows polynomially. That crossover is the computational advantage this platform is built to measure.",
  );
  return parts.join(" ");
}

export default function ComparisonPanel({ result }: { result: BenchmarkResult }) {
  const qualities = PATHS.map(({ key }) => quality(result.paths[key]));
  const bestQuality = Math.max(...qualities);
  const isMaxcut = result.algorithm === "maxcut-qaoa";

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
                <span className="k">wall time</span>
                <span className="v">{formatSeconds(path.elapsed_seconds)}</span>
              </div>
              {isMaxcut && path.cut !== undefined && (
                <div className="metric-row">
                  <span className="k">cut found</span>
                  <span className="v">
                    {path.cut} / {result.optimal.cut}
                  </span>
                </div>
              )}
              {!isMaxcut && path.energy !== undefined && (
                <div className="metric-row">
                  <span className="k">energy</span>
                  <span className="v">{path.energy.toFixed(5)}</span>
                </div>
              )}
              {!isMaxcut && result.optimal.energy !== undefined && (
                <div className="metric-row">
                  <span className="k">exact ground</span>
                  <span className="v">{result.optimal.energy.toFixed(5)}</span>
                </div>
              )}
              {(path.circuit_evaluations ?? path.evaluations) !== undefined && (
                <div className="metric-row">
                  <span className="k">evaluations</span>
                  <span className="v">{(path.circuit_evaluations ?? path.evaluations)?.toLocaleString()}</span>
                </div>
              )}
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
