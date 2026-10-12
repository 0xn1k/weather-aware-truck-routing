import type { RouteResult } from "@/api/types";
import { formatAvgRisk, formatClock, formatDuration, formatMiles } from "@/lib/format";
import { SectionHeader } from "@/lib/SectionHeader";
import { CheckCircleIcon, ClockIcon, DotsIcon, FlagIcon, RouteIcon, WarningIcon } from "@/lib/icons";

interface TripSummaryKpisProps {
  route: RouteResult;
  /** The A/B/C letter RouteList/StartEndMarkers/the map pin already use for
   * this route — shown alongside the label so this tile answers "which one
   * of the 3 routes is this?", not just "what kind of route is it?". */
  letter: string;
  departureIso: string;
}

export function TripSummaryKpis({ route, letter, departureIso }: TripSummaryKpisProps) {
  const hasRisk = route.summary.miles_by_level.severe > 0 || route.summary.miles_by_level.no_travel > 0;

  const tiles = [
    {
      icon: CheckCircleIcon,
      label: "Recommended route",
      value: letter ? `${letter} · ${route.label}` : route.label,
    },
    { icon: RouteIcon, label: "Distance", value: formatMiles(route.distance_mi) },
    { icon: ClockIcon, label: "Drive time", value: formatDuration(route.duration_s) },
    { icon: FlagIcon, label: "Departs", value: formatClock(departureIso) },
    { icon: DotsIcon, label: "Checkpoints", value: String(route.checkpoints.length) },
    {
      icon: WarningIcon,
      label: "Average risk",
      value: formatAvgRisk(route.summary.avg_risk),
      warn: hasRisk,
    },
  ];

  return (
    <section
      aria-label="Trip summary"
      className="rounded-[20px] p-6"
      style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
    >
      <SectionHeader>Trip summary · recommended route</SectionHeader>
      <div className="mt-[18px] grid grid-cols-2 gap-3 sm:grid-cols-3">
        {tiles.map(({ icon: Icon, label, value, warn }) => (
          <div
            key={label}
            className="flex min-w-0 items-center gap-3 rounded-[14px] p-3.5"
            style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}
          >
            <span
              className="flex h-10 w-10 flex-none items-center justify-center rounded-[11px]"
              style={{
                background: warn ? "var(--risk-3-tint)" : "var(--accent-tint)",
                color: warn ? "var(--risk-3)" : "var(--accent)",
              }}
            >
              <Icon size={19} />
            </span>
            <div className="min-w-0">
              <div className="truncate text-xs" style={{ color: "var(--muted)" }}>
                {label}
              </div>
              <div
                className="truncate text-[15px] font-semibold"
                style={{ color: warn ? "var(--bad)" : "var(--ink)" }}
              >
                {value}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
