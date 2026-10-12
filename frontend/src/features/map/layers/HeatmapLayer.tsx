import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import type { HeatmapGrid } from "@/api/types";

interface HeatmapLayerProps {
  grid: HeatmapGrid;
  hour: number;
  /** The layer id this must render directly below — the selected route's
   * casing (see TripMap.tsx). NOT CHECKPOINT_LAYER_ID: the heatmap loads
   * asynchronously, well after the route layers already exist, and
   * anchoring to the same target as the routes meant whichever one's
   * layer was (re-)inserted more recently won the spot closer to the
   * checkpoints — which was almost always the heatmap, since it mounts
   * later. That put the colour wash on TOP of the route line instead of
   * under it. Anchoring to the route's own casing guarantees the heatmap
   * always ends up below every route, not just below the checkpoints. */
  beforeId: string;
}

/** MapLibre's native heatmap type, weighted by risk/4 at the current slider
 * hour (top-level README.md Section 6: "Moving the slider updates one
 * GeoJSON source with that hour's weights"). */
export function HeatmapLayer({ grid, hour, beforeId }: HeatmapLayerProps) {
  const geojson: GeoJSON.FeatureCollection = useMemo(() => {
    const riskRow = grid.risk_levels[hour] ?? [];
    return {
      type: "FeatureCollection",
      features: grid.points.map(([lat, lon], index) => ({
        type: "Feature" as const,
        properties: { weight: (riskRow[index] ?? 0) / 4 },
        geometry: { type: "Point" as const, coordinates: [lon, lat] },
      })),
    };
  }, [grid, hour]);

  return (
    <Source id="heatmap-source" type="geojson" data={geojson}>
      <Layer
        id="heatmap"
        type="heatmap"
        beforeId={beforeId}
        paint={{
          // The corridor grid is sparse (~100 points spread across a wide
          // area, most hours only a handful nonzero) — MapLibre's heatmap
          // density comes from overlapping point kernels, so an isolated
          // risky point with the old low intensity/radius/opacity never
          // built up enough density to clear the colour ramp's first stop
          // and rendered as nothing. These values are tuned so a SINGLE
          // point is clearly visible on its own, not just a dense cluster.
          "heatmap-weight": ["get", "weight"],
          "heatmap-intensity": 1.6,
          "heatmap-radius": 55,
          "heatmap-opacity": 0.8,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(0,0,0,0)",
            0.08,
            "#22A05A",
            0.3,
            "#E8B21F",
            0.55,
            "#F07C1F",
            0.75,
            "#D93A2E",
            0.95,
            "#6D35A8",
          ],
        }}
      />
    </Source>
  );
}
