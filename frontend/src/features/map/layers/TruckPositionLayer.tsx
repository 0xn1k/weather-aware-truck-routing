import { useMemo } from "react";
import { Marker } from "react-map-gl/maplibre";
import type { RouteResult } from "@/api/types";
import { haversineMi } from "@/lib/geo";
import { TruckIcon } from "@/lib/icons";

interface TruckPositionLayerProps {
  route: RouteResult;
  departureIso: string;
  hour: number;
}

interface GeometryStep {
  lon: number;
  lat: number;
  cumulativeMi: number;
}

function buildCumulativeMiles(coordinates: [number, number][]): GeometryStep[] {
  const steps: GeometryStep[] = [];
  let cumulative = 0;
  for (let i = 0; i < coordinates.length; i++) {
    const [lon, lat] = coordinates[i];
    if (i > 0) {
      const [prevLon, prevLat] = coordinates[i - 1];
      cumulative += haversineMi({ lat: prevLat, lon: prevLon }, { lat, lon });
    }
    steps.push({ lon, lat, cumulativeMi: cumulative });
  }
  return steps;
}

function pointAtMile(steps: GeometryStep[], targetMile: number): { lon: number; lat: number } {
  if (steps.length === 0) return { lon: 0, lat: 0 };
  const first = steps[0];
  const last = steps[steps.length - 1];
  if (targetMile <= first.cumulativeMi) return first;
  if (targetMile >= last.cumulativeMi) return last;

  for (let i = 0; i < steps.length - 1; i++) {
    const a = steps[i];
    const b = steps[i + 1];
    if (targetMile >= a.cumulativeMi && targetMile <= b.cumulativeMi) {
      const span = b.cumulativeMi - a.cumulativeMi;
      const fraction = span > 0 ? (targetMile - a.cumulativeMi) / span : 0;
      return { lon: a.lon + (b.lon - a.lon) * fraction, lat: a.lat + (b.lat - a.lat) * fraction };
    }
  }
  return last;
}

/** Follows the route's actual drawn geometry, not a straight line between
 * the two bracketing checkpoints — checkpoints can be many miles apart
 * (interval_miles) on a curving road, and a direct lat/lon lerp between
 * them visibly cuts across the curve instead of tracking the line. This
 * finds the checkpoint pair bracketing the target time, time-interpolates
 * the MILE position between them, then walks the geometry to that exact
 * mile — the same "position by mile along geometry" approach the backend's
 * core/sampling.py uses to place checkpoints in the first place, so the
 * truck always sits exactly on the visible route line. */
export function TruckPositionLayer({ route, departureIso, hour }: TruckPositionLayerProps) {
  // eslint-disable-next-line react-hooks/exhaustive-deps -- coordinates array is stable per route
  const steps = useMemo(() => buildCumulativeMiles(route.geometry.coordinates), [route.id]);

  const checkpoints = route.checkpoints;
  if (checkpoints.length === 0) return null;

  const targetMs = new Date(departureIso).getTime() + hour * 3_600_000;
  let before = checkpoints[0];
  let after = checkpoints[checkpoints.length - 1];
  for (let i = 0; i < checkpoints.length - 1; i++) {
    const a = checkpoints[i];
    const b = checkpoints[i + 1];
    if (new Date(a.eta).getTime() <= targetMs && targetMs <= new Date(b.eta).getTime()) {
      before = a;
      after = b;
      break;
    }
  }

  const beforeMs = new Date(before.eta).getTime();
  const afterMs = new Date(after.eta).getTime();
  const fraction = afterMs > beforeMs ? (targetMs - beforeMs) / (afterMs - beforeMs) : 0;
  const clamped = Math.max(0, Math.min(1, fraction));
  const targetMile = before.mile + (after.mile - before.mile) * clamped;
  const { lon, lat } = pointAtMile(steps, targetMile);

  return (
    <Marker longitude={lon} latitude={lat} anchor="center">
      <span
        className="flex h-8 w-8 items-center justify-center rounded-full"
        style={{ background: "var(--accent)", color: "var(--on-accent)", boxShadow: "var(--shadow)" }}
        aria-label={`Route ${route.id} truck position`}
      >
        <TruckIcon size={16} />
      </span>
    </Marker>
  );
}
