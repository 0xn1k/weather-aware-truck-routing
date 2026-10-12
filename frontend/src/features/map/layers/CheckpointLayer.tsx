import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import type { RouteResult } from "@/api/types";
import { RISK_LEVELS } from "@/lib/risk";
import { cssVar } from "@/lib/theme";

interface CheckpointLayerProps {
  route: RouteResult;
  themeVersion: string;
}

export const CHECKPOINT_LAYER_ID = "checkpoints";

/** Click handling for this layer lives at the <Map> level in TripMap.tsx
 * via interactiveLayerIds — react-map-gl's <Layer> doesn't take its own
 * onClick. */
export function CheckpointLayer({ route, themeVersion }: CheckpointLayerProps) {
  const geojson: GeoJSON.FeatureCollection = useMemo(
    () => ({
      type: "FeatureCollection",
      features: route.checkpoints.map((cp, index) => ({
        type: "Feature",
        properties: { index, risk: cp.risk },
        geometry: { type: "Point", coordinates: [cp.lon, cp.lat] },
      })),
    }),
    [route],
  );

  const colorExpression = useMemo(
    () => [
      "match",
      ["get", "risk"],
      ...RISK_LEVELS.flatMap((level) => [level, cssVar(`--risk-${RISK_LEVELS.indexOf(level)}`)]),
      cssVar("--risk-0"),
    ],
    // themeVersion forces a recompute on theme toggle even though cssVar()
    // reads the DOM directly rather than referencing the variable itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [themeVersion],
  );

  return (
    <Source id="checkpoints-source" type="geojson" data={geojson}>
      <Layer
        id={CHECKPOINT_LAYER_ID}
        type="circle"
        paint={{
          "circle-radius": 6,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          "circle-color": colorExpression as any,
          "circle-stroke-width": 1.8,
          "circle-stroke-color": cssVar("--bg"),
        }}
      />
    </Source>
  );
}
