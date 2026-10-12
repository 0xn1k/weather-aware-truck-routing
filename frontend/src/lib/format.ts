import { RISK_LEVELS } from "./risk";

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString()} mi`;
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} min`;
  if (minutes === 0) return `${hours} h`;
  return `${hours} h ${minutes} min`;
}

/** UTC ISO timestamp -> the viewer's local time, e.g. "Tue 14:00"
 * (top-level README.md design principle 6: UTC inside, local time on screen). */
export function formatClock(isoUtc: string): string {
  return new Date(isoUtc).toLocaleTimeString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatHourOffset(hour: number, departureIsoUtc: string): string {
  const at = new Date(new Date(departureIsoUtc).getTime() + hour * 3_600_000);
  const clock = at.toLocaleTimeString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `+${hour} h · ${clock}`;
}

export function formatLoad(lb: number): string {
  return `${Math.round(lb).toLocaleString()} lb`;
}

// avg_risk is a distance-weighted average of RiskLevel's own ordinal values
// (Low=0 .. No travel=4, RISK_LEVELS below), not a 0-1 fraction — showing
// "/4" makes that scale explicit instead of a bare decimal that reads like
// a percentage.
const MAX_AVG_RISK = RISK_LEVELS.length - 1;

export function formatAvgRisk(avgRisk: number): string {
  return `${avgRisk.toFixed(2)}/${MAX_AVG_RISK}`;
}
