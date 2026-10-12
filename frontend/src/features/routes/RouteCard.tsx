import type { RouteResult } from "@/api/types";
import { formatAvgRisk, formatClock, formatDuration, formatMiles } from "@/lib/format";
import { RiskBar } from "./RiskBar";

interface RouteCardProps {
  route: RouteResult;
  letter: string;
  totalRoutes: number;
  isSelected: boolean;
  isRecommended: boolean;
  isFastest: boolean;
  onSelect: () => void;
  onOpenDetails: () => void;
}

export function RouteCard({
  route,
  letter,
  totalRoutes,
  isSelected,
  isRecommended,
  isFastest,
  onSelect,
  onOpenDetails,
}: RouteCardProps) {
  return (
    <article
      className="rounded-2xl p-[18px]"
      style={{
        border: `${isSelected ? 2 : 1}px solid ${isSelected ? "var(--accent)" : "var(--line)"}`,
        background: "var(--surface)",
        boxShadow: isSelected ? "var(--shadow)" : "none",
      }}
    >
      <div className="flex flex-wrap items-center gap-2.5">
        <span
          className="flex h-[30px] w-[30px] flex-none items-center justify-center rounded-full text-sm font-bold"
          style={{
            background: isSelected ? "var(--accent)" : "var(--chip)",
            color: isSelected ? "var(--on-accent)" : "var(--ink)",
          }}
        >
          {letter}
        </span>
        <h3 className="m-0 text-[17px] font-bold" style={{ color: "var(--ink)" }}>
          Route {letter}
        </h3>
        {isRecommended && (
          <span
            className="rounded-full px-2.5 py-1 text-xs font-semibold"
            style={{ background: "var(--rec-bg)", color: "var(--rec-ink)" }}
          >
            Recommended
          </span>
        )}
        {isFastest && (
          <span
            className="rounded-full px-2.5 py-1 text-xs font-semibold"
            style={{ background: "var(--chip)", color: "var(--ink)" }}
          >
            Fastest
          </span>
        )}
        <span className="ml-auto text-xs font-semibold" style={{ color: "var(--muted)" }}>
          Rank {route.rank} of {totalRoutes}
        </span>
      </div>

      <div className="mt-1.5 text-sm" style={{ color: "var(--muted)" }}>
        {route.label}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <Stat label="Distance" value={formatMiles(route.distance_mi)} />
        <Stat label="Drive time" value={formatDuration(route.duration_s)} />
        <Stat label="Arrives" value={formatClock(route.arrival_time)} />
        <Stat
          label="Avg risk"
          value={formatAvgRisk(route.summary.avg_risk)}
          warn={route.summary.miles_by_level.severe > 0 || route.summary.miles_by_level.no_travel > 0}
        />
      </div>

      <div className="mt-4">
        <RiskBar milesByLevel={route.summary.miles_by_level} />
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={onSelect}
          className="h-11 flex-1 rounded-[10px] text-sm font-semibold"
          style={{
            background: isSelected ? "var(--accent-tint)" : "var(--surface)",
            color: isSelected ? "var(--accent)" : "var(--ink)",
            border: "1px solid var(--line)",
          }}
        >
          {isSelected ? "Shown on map" : "Show on map"}
        </button>
        <button
          type="button"
          onClick={onOpenDetails}
          className="h-11 flex-1 rounded-[10px] text-sm font-semibold"
          style={{ background: "var(--btn)", color: "var(--on-btn)" }}
        >
          Full details
        </button>
      </div>
    </article>
  );
}

function Stat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs" style={{ color: "var(--muted)" }}>
        {label}
      </div>
      <div
        className="mt-0.5 text-[15px] font-semibold"
        style={{ color: warn ? "var(--bad)" : "var(--ink)" }}
      >
        {value}
      </div>
    </div>
  );
}
