import { Marker } from "react-map-gl/maplibre";
import type { RouteResult } from "@/api/types";
import { RoutePin } from "./RoutePin";

interface StartEndMarkersProps {
  route: RouteResult;
  originLabel?: string;
  destinationLabel?: string;
}

/** Teardrop pins at the route's true endpoints (route.geometry's first and
 * last coordinate — not a sampled checkpoint), so the start and end of the
 * trip read clearly against the route line and risk-coloured checkpoints. */
export function StartEndMarkers({ route, originLabel, destinationLabel }: StartEndMarkersProps) {
  const coords = route.geometry.coordinates;
  if (coords.length === 0) return null;
  const [startLon, startLat] = coords[0];
  const [endLon, endLat] = coords[coords.length - 1];

  return (
    <>
      <Marker longitude={startLon} latitude={startLat} anchor="bottom">
        <div style={{ transform: "translateY(-2px)" }}>
          <RoutePin label="A" fill="var(--ink)" ink="var(--bg)" title={originLabel ?? "Start"} />
        </div>
      </Marker>
      <Marker longitude={endLon} latitude={endLat} anchor="bottom">
        <div style={{ transform: "translateY(-2px)" }}>
          <RoutePin
            label="B"
            fill="var(--accent)"
            ink="var(--on-accent)"
            title={destinationLabel ?? "Destination"}
          />
        </div>
      </Marker>
    </>
  );
}
