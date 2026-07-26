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

export interface ConvergencePoint {
  iteration: number;
  value: number;
  best: number;
}

interface Props {
  points: ConvergencePoint[];
  target?: number;
  targetLabel: string;
  yLabel: string;
}

export default function ConvergenceChart({ points, target, targetLabel, yLabel }: Props) {
  if (points.length === 0) {
    return <div className="placeholder">The hybrid optimization trace will appear here.</div>;
  }
  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#232a38" strokeDasharray="3 3" />
          <XAxis
            dataKey="iteration"
            stroke="#8b94a7"
            fontSize={11}
            label={{ value: "circuit evaluation", position: "insideBottom", offset: -2, fontSize: 11, fill: "#8b94a7" }}
          />
          <YAxis stroke="#8b94a7" fontSize={11} domain={["auto", "auto"]} tickFormatter={(v: number) => v.toFixed(2)} />
          <Tooltip
            contentStyle={{ background: "#171c27", border: "1px solid #232a38", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#8b94a7" }}
            formatter={(value) => (typeof value === "number" ? value.toFixed(4) : String(value))}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="value" name={yLabel} stroke="#6d5efc" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line type="monotone" dataKey="best" name={`best ${yLabel}`} stroke="#34d399" dot={false} strokeWidth={2} isAnimationActive={false} />
          {target !== undefined && (
            <ReferenceLine
              y={target}
              stroke="#22d3ee"
              strokeDasharray="6 4"
              label={{ value: targetLabel, fill: "#22d3ee", fontSize: 11, position: "insideTopRight" }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
      <div className="chart-caption">
        Each point is a real quantum circuit evaluation requested by the classical optimizer.
      </div>
    </div>
  );
}
