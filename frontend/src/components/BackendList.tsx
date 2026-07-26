import type { BackendInfo } from "../types";

const MODE_LABEL: Record<string, string> = {
  connected: "ready",
  simulated: "simulated",
  not_configured: "no credentials",
  unavailable: "unavailable",
};

interface Props {
  backends: BackendInfo[];
  selected: string;
  onSelect: (id: string) => void;
}

export default function BackendList({ backends, selected, onSelect }: Props) {
  const selectedInfo = backends.find((b) => b.id === selected);
  return (
    <div>
      <div className="backend-list">
        {backends.map((backend) => {
          const runnable = backend.mode === "connected" || backend.mode === "simulated";
          return (
            <div
              key={backend.id}
              className={
                "backend-card" +
                (backend.id === selected ? " selected" : "") +
                (runnable ? "" : " disabled")
              }
              onClick={() => runnable && onSelect(backend.id)}
              title={backend.mode_detail}
            >
              <span className={`mode-dot ${backend.mode}`} />
              <div>
                <div className="b-name">{backend.name}</div>
                <div className="b-vendor">{backend.vendor}</div>
              </div>
              <span className="mode-tag">{MODE_LABEL[backend.mode] ?? backend.mode}</span>
            </div>
          );
        })}
      </div>
      {selectedInfo && (
        <div className="backend-detail">
          <strong>{selectedInfo.name}</strong> — {selectedInfo.description}
          <br />
          <span style={{ opacity: 0.8 }}>{selectedInfo.mode_detail}</span>
        </div>
      )}
    </div>
  );
}
