import { AnimatePresence, motion } from "framer-motion";
import type { RouteResult } from "@/api/types";
import { formatAvgRisk, formatClock, formatDuration, formatMiles } from "@/lib/format";
import { CloseIcon } from "@/lib/icons";
import { RISK_LABELS, riskColorVar, type RiskLevelName } from "@/lib/risk";
import { scaleFade } from "@/lib/motion";
import { RiskBar } from "./RiskBar";

interface RouteDetailsModalProps {
  route: RouteResult;
  letter: string;
  onClose: () => void;
}

export function RouteDetailsModal({ route, letter, onClose }: RouteDetailsModalProps) {
  const { summary } = route;

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8"
        style={{ background: "rgba(0,0,0,0.5)" }}
        onClick={onClose}
      >
        <motion.div
          variants={scaleFade}
          initial="hidden"
          animate="visible"
          exit="hidden"
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-3xl rounded-[20px] p-6"
          style={{ background: "var(--surface)", boxShadow: "var(--shadow)" }}
          role="dialog"
          aria-modal="true"
          aria-label={`Route ${letter} details`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}
              >
                {letter}
              </span>
              <div>
                <h2 className="m-0 text-lg font-bold" style={{ color: "var(--ink)" }}>
                  Route {letter} · {route.label}
                </h2>
                <div className="text-sm" style={{ color: "var(--muted)" }}>
                  Rank {route.rank}
                </div>
              </div>
            </div>
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              className="h-11 w-11 flex-none rounded-[10px]"
              style={{ border: "1px solid var(--line)", color: "var(--ink)" }}
            >
              <CloseIcon className="mx-auto" />
            </button>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Tile label="Distance" value={formatMiles(route.distance_mi)} />
            <Tile label="Drive time" value={formatDuration(route.duration_s)} />
            <Tile label="Arrives" value={formatClock(route.arrival_time)} />
            <Tile label="Checkpoints" value={String(route.checkpoints.length)} />
            <Tile label="Average risk" value={formatAvgRisk(summary.avg_risk)} />
            <Tile label="Worst level" value={RISK_LABELS[summary.max_level]} />
          </div>

          <div className="mt-6">
            <h3 className="m-0 text-sm font-bold" style={{ color: "var(--ink)" }}>
              Risk along the route
            </h3>
            <div className="mt-2">
              <RiskBar milesByLevel={summary.miles_by_level} height={14} />
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
              {(Object.keys(summary.miles_by_level) as RiskLevelName[]).map((level) => (
                <span key={level} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: riskColorVar(level) }}
                  />
                  {RISK_LABELS[level]}: {Math.round(summary.miles_by_level[level])} mi
                </span>
              ))}
            </div>
          </div>

          <div className="mt-6">
            <h3 className="m-0 text-sm font-bold" style={{ color: "var(--ink)" }}>
              Worst stop
            </h3>
            <p className="m-0 mt-1.5 text-sm" style={{ color: "var(--ink)" }}>
              Mile {Math.round(summary.worst_checkpoint.mile)}, arriving{" "}
              {formatClock(summary.worst_checkpoint.eta)} — {RISK_LABELS[summary.worst_checkpoint.risk]}
              , driven by {summary.worst_checkpoint.driver}.
            </p>
          </div>

          <div className="mt-6">
            <h3 className="m-0 text-sm font-bold" style={{ color: "var(--ink)" }}>
              Weather extremes on this route
            </h3>
            <div className="mt-2 grid grid-cols-3 gap-3">
              <Tile label="Peak wind" value={`${summary.peak_wind.value.toFixed(1)} mph`} />
              <Tile label="Peak rain" value={`${summary.peak_rain.value.toFixed(2)} in/hr`} />
              <Tile label="Peak snow" value={`${summary.peak_snow.value.toFixed(1)} in/hr`} />
            </div>
          </div>

          <div className="mt-6">
            <h3 className="m-0 text-sm font-bold" style={{ color: "var(--ink)" }}>
              Every checkpoint
            </h3>
            <div className="mt-2 max-h-64 overflow-y-auto rounded-xl" style={{ border: "1px solid var(--line)" }}>
              <table className="w-full border-collapse text-xs">
                <thead style={{ background: "var(--surface-2)" }}>
                  <tr>
                    {["Mile", "Arrival", "Wind", "Rain", "Snow", "Level"].map((h) => (
                      <th key={h} className="px-3 py-2 text-left font-semibold" style={{ color: "var(--muted)" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {route.checkpoints.map((cp) => (
                    <tr
                      key={cp.mile}
                      style={{
                        background:
                          cp.risk === "high" || cp.risk === "severe" || cp.risk === "no_travel"
                            ? "var(--risk-2-tint)"
                            : undefined,
                        borderTop: "1px solid var(--line-2)",
                      }}
                    >
                      <td className="px-3 py-2" style={{ color: "var(--ink)" }}>
                        {Math.round(cp.mile)}
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--ink)" }}>
                        {formatClock(cp.eta)}
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--ink)" }}>
                        {cp.wind_mph.toFixed(0)} mph
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--ink)" }}>
                        {cp.rain_in_hr.toFixed(2)}&Prime;/hr
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--ink)" }}>
                        {cp.snow_in_hr.toFixed(1)}&Prime;/hr
                      </td>
                      <td className="px-3 py-2 font-semibold" style={{ color: riskColorVar(cp.risk) }}>
                        {RISK_LABELS[cp.risk]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl p-3" style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}>
      <div className="text-xs" style={{ color: "var(--muted)" }}>
        {label}
      </div>
      <div className="mt-0.5 text-sm font-semibold" style={{ color: "var(--ink)" }}>
        {value}
      </div>
    </div>
  );
}
