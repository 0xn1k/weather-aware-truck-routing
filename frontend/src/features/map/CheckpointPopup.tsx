import { Popup } from "react-map-gl/maplibre";
import type { Checkpoint } from "@/api/types";
import { formatClock } from "@/lib/format";
import { RISK_LABELS, riskColorVar } from "@/lib/risk";

interface CheckpointPopupProps {
  checkpoint: Checkpoint;
  onClose: () => void;
}

export function CheckpointPopup({ checkpoint, onClose }: CheckpointPopupProps) {
  return (
    <Popup
      longitude={checkpoint.lon}
      latitude={checkpoint.lat}
      onClose={onClose}
      closeButton={false}
      anchor="bottom"
      offset={14}
    >
      <div className="min-w-[180px] p-1" style={{ color: "var(--ink)" }}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-bold">Mile {Math.round(checkpoint.mile)}</span>
          <span
            className="rounded-full px-2 py-0.5 text-xs font-semibold"
            style={{ background: riskColorVar(checkpoint.risk), color: "var(--on-accent)" }}
          >
            {RISK_LABELS[checkpoint.risk]}
          </span>
        </div>
        <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          Arrives {formatClock(checkpoint.eta)}
        </div>
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt style={{ color: "var(--muted)" }}>Wind</dt>
          <dd className="m-0">{checkpoint.wind_mph.toFixed(0)} mph</dd>
          <dt style={{ color: "var(--muted)" }}>Gust</dt>
          <dd className="m-0">{checkpoint.gust_mph.toFixed(0)} mph</dd>
          <dt style={{ color: "var(--muted)" }}>Rain</dt>
          <dd className="m-0">{checkpoint.rain_in_hr.toFixed(2)} in/hr</dd>
          <dt style={{ color: "var(--muted)" }}>Snow</dt>
          <dd className="m-0">{checkpoint.snow_in_hr.toFixed(1)} in/hr</dd>
        </dl>
        <div className="mt-1.5 text-xs" style={{ color: "var(--muted)" }}>
          Set by {checkpoint.driver}
        </div>
      </div>
    </Popup>
  );
}
