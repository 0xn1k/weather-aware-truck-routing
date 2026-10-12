import type { TripPlanRequest } from "@/api/types";
import { formatClock, formatLoad } from "@/lib/format";
import { ExpandIcon } from "@/lib/icons";

interface MiniTripSummaryProps {
  request: TripPlanRequest;
  onExpand: () => void;
}

/** Shown in place of the full TripForm once the sidebar is collapsed
 * (App.tsx) — "I already planned this trip, let me see the map" rather
 * than "I need to change something", so it's read-only: the From/To/
 * departure/load that were actually submitted, plus a way back to the
 * editable form. */
export function MiniTripSummary({ request, onExpand }: MiniTripSummaryProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <span
          className="mt-1.5 h-2 w-2 flex-none rounded-full"
          style={{ background: "var(--accent)" }}
        />
        <span className="min-w-0 truncate text-[13.5px] font-semibold" style={{ color: "var(--ink)" }}>
          {request.origin.label}
        </span>
      </div>
      <div className="flex items-start gap-2">
        <span
          className="mt-1.5 h-2 w-2 flex-none rounded-full"
          style={{ background: "var(--risk-3)" }}
        />
        <span className="min-w-0 truncate text-[13.5px] font-semibold" style={{ color: "var(--ink)" }}>
          {request.destination.label}
        </span>
      </div>
      <div className="text-[12px] leading-relaxed" style={{ color: "var(--muted)" }}>
        {formatClock(request.departure_time)}
        <br />
        {formatLoad(request.load_weight_lb)}
      </div>
      <button
        type="button"
        onClick={onExpand}
        className="mt-1 flex h-9 w-full items-center justify-center gap-1.5 rounded-[10px] text-[12.5px] font-semibold"
        style={{ border: "1px solid var(--line)", color: "var(--ink)", background: "var(--surface-2)" }}
      >
        <ExpandIcon size={13} />
        Edit trip
      </button>
    </div>
  );
}
