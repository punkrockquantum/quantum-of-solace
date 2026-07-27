import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchAlgorithms, fetchBackends, fetchJob, submitJob } from "./api";
import BackendList from "./components/BackendList";
import ComparisonPanel from "./components/ComparisonPanel";
import ConvergenceChart, { type ConvergencePoint } from "./components/ConvergenceChart";
import ProjectionPanel from "./components/ProjectionPanel";
import type { Algorithm, BackendInfo, BenchmarkResult, ProgressEvent } from "./types";

type RunState = "idle" | "running" | "done" | "error";

export default function App() {
  const [backends, setBackends] = useState<BackendInfo[]>([]);
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [algorithmId, setAlgorithmId] = useState("");
  const [backendId, setBackendId] = useState("local-simulator");
  const [params, setParams] = useState<Record<string, number>>({});
  const [runState, setRunState] = useState<RunState>("idle");
  const [error, setError] = useState("");
  const [feed, setFeed] = useState<{ phase: string; message: string }[]>([]);
  const [points, setPoints] = useState<ConvergencePoint[]>([]);
  const [target, setTarget] = useState<number | undefined>(undefined);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const algorithm = useMemo(
    () => algorithms.find((a) => a.id === algorithmId),
    [algorithms, algorithmId],
  );

  useEffect(() => {
    Promise.all([fetchBackends(), fetchAlgorithms()])
      .then(([backendList, algorithmList]) => {
        setBackends(backendList);
        setAlgorithms(algorithmList);
        if (algorithmList.length > 0) {
          setAlgorithmId(algorithmList[0].id);
          setParams(Object.fromEntries(algorithmList[0].params.map((p) => [p.id, p.default])));
        }
      })
      .catch((err: Error) => setError(`Could not reach the backend at /api - is it running? (${err.message})`));
    return () => eventSourceRef.current?.close();
  }, []);

  const selectAlgorithm = useCallback(
    (id: string) => {
      setAlgorithmId(id);
      const next = algorithms.find((a) => a.id === id);
      if (next) setParams(Object.fromEntries(next.params.map((p) => [p.id, p.default])));
    },
    [algorithms],
  );

  const run = useCallback(async () => {
    if (!algorithm) return;
    setRunState("running");
    setError("");
    setFeed([]);
    setPoints([]);
    setTarget(undefined);
    setResult(null);
    try {
      const job = await submitJob(algorithm.id, backendId, params);
      const source = new EventSource(`/api/jobs/${job.id}/events`);
      eventSourceRef.current = source;

      source.onmessage = (message) => {
        const event = JSON.parse(message.data) as ProgressEvent;
        if (event.type === "progress") {
          if (event.message) {
            setFeed((old) => [{ phase: event.phase ?? "", message: event.message! }, ...old].slice(0, 80));
          }
          if (event.phase === "hybrid" && event.iteration !== undefined && event.value !== undefined) {
            setPoints((old) => [...old, { iteration: event.iteration!, value: event.value!, best: event.best ?? event.value! }]);
            if (event.target !== undefined) setTarget(event.target);
          }
        }
        if (event.type === "status" && event.status === "failed") {
          setError(event.error ?? "job failed");
          setRunState("error");
        }
      };

      source.addEventListener("end", async () => {
        source.close();
        const finished = await fetchJob(job.id);
        if (finished.status === "completed" && finished.result) {
          setResult(finished.result);
          setRunState("done");
        } else {
          setError(finished.error ?? "job did not complete");
          setRunState("error");
        }
      });

      source.onerror = () => {
        source.close();
        setRunState((state) => (state === "running" ? "error" : state));
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setRunState("error");
    }
  }, [algorithm, backendId, params]);

  const chartLabels: Record<string, { y: string; target: string }> = {
    "maxcut-qaoa": { y: "expected cut", target: "exact optimum" },
    "vqe-ising": { y: "energy", target: "exact ground energy" },
    "quantum-monte-carlo": { y: "estimate", target: "true value" },
    "cfd-vqls": { y: "fidelity", target: "exact solution" },
    "gbs-dense-subgraph": { y: "density", target: "densest subgraph" },
  };
  const labels = chartLabels[algorithm?.id ?? ""] ?? { y: "value", target: "target" };

  return (
    <div className="app">
      <header className="header">
        <h1>Quantum of Solace</h1>
        <span className="tagline">
          Hybrid quantum-classical orchestration — measured against exact classical ground truth.
        </span>
      </header>

      <div className="layout">
        {/* ---------- left column: configuration ---------- */}
        <div className="stack">
          <section className="panel">
            <h2>1 · Choose a problem</h2>
            <div className="field">
              <select value={algorithmId} onChange={(e) => selectAlgorithm(e.target.value)}>
                {algorithms.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            {algorithm && <p className="algo-summary">{algorithm.summary}</p>}
            {algorithm && (
              <div className="param-grid">
                {algorithm.params.map((p) => (
                  <div className="field" key={p.id}>
                    <label>{p.label}</label>
                    <input
                      type="number"
                      value={params[p.id] ?? p.default}
                      min={p.min}
                      max={p.max}
                      step={p.type === "int" ? 1 : 0.1}
                      onChange={(e) =>
                        setParams((old) => ({ ...old, [p.id]: Number(e.target.value) }))
                      }
                    />
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="panel">
            <h2>2 · Choose where quantum circuits run</h2>
            <BackendList backends={backends} selected={backendId} onSelect={setBackendId} />
          </section>

          <button className="run-button" onClick={run} disabled={runState === "running" || !algorithm}>
            {runState === "running" ? (
              <>
                <span className="spin" />
                Running classical · quantum · hybrid...
              </>
            ) : (
              "Run comparison"
            )}
          </button>
        </div>

        {/* ---------- right column: results ---------- */}
        <div className="stack">
          {error && <div className="error-banner">{error}</div>}

          <section className="panel">
            <h2>Hybrid optimization — live</h2>
            <ConvergenceChart points={points} target={target} targetLabel={labels.target} yLabel={labels.y} />
            {feed.length > 0 && (
              <div className="feed" style={{ marginTop: 12 }}>
                {feed.map((entry, i) => (
                  <div key={feed.length - i}>
                    <span className="phase">[{entry.phase}]</span> {entry.message}
                  </div>
                ))}
              </div>
            )}
          </section>

          {result ? (
            <>
              <ComparisonPanel result={result} />
              {result.projection && <ProjectionPanel projection={result.projection} />}
            </>
          ) : (
            runState !== "running" && (
              <section className="panel">
                <div className="placeholder">
                  Pick a problem and press <strong>Run comparison</strong>. The same problem is solved
                  three ways — pure classical (exact), pure quantum, and hybrid — and every number shown
                  is measured, never estimated.
                </div>
              </section>
            )
          )}
        </div>
      </div>
    </div>
  );
}
