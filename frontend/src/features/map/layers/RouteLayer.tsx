import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import type { RouteResult } from "@/api/types";
import { cssVar } from "@/lib/theme";
import { CHECKPOINT_LAYER_ID } from "./CheckpointLayer";

interface RouteLayerProps {
  routes: RouteResult[];
  selectedRouteId: string;
  /** Re-renders paint colours when the theme toggles — MapLibre paint
   * properties need resolved colour strings, not CSS var(). */
  themeVersion: string;
}

/** Dark casing under a coloured line — selected route wider and in accent,
 * others thinner and grey (frontend/README.md Section 9.8).
 *
 * Z-order is driven entirely by `beforeId`, not by JSX order: react-map-gl's
 * <Layer> only calls map.moveLayer() when its `beforeId` prop VALUE changes
 * between renders — re-rendering routes in a different JSX order does
 * nothing once the underlying MapLibre layers already exist. So:
 *   - the selected route's layers anchor to CHECKPOINT_LAYER_ID (always on
 *     top of every other route, directly below the checkpoint dots —
 *     NOT `beforeId: undefined`, which means "move to the very top of the
 *     whole style" and hid the checkpoint dots under the route line);
 *   - every unselected route's layers anchor to the SELECTED route's
 *     casing id, so they sit directly below whichever route is selected.
 * Both of those targets change value exactly when selection changes,
 * which is what makes moveLayer actually fire on every switch.
 *
 * Creation-order hazard: MapLibre's addLayer() throws if `beforeId` names a
 * layer that doesn't exist yet. CHECKPOINT_LAYER_ID is guaranteed to exist
 * because TripMap.tsx mounts CheckpointLayer before this component; the
 * selected route's casing is guaranteed to exist before any unselected
 * route references it because `ordered` below always processes the
 * selected route first. */
export function RouteLayer({ routes, selectedRouteId, themeVersion }: RouteLayerProps) {
  // eslint-disable-next-line react-hooks/exhaustive-deps -- re-resolve colours on theme change
  const casingColor = useMemo(() => cssVar("--casing"), [themeVersion]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const accentColor = useMemo(() => cssVar("--accent"), [themeVersion]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const otherColor = useMemo(() => cssVar("--route-other"), [themeVersion]);
  // In dark mode --casing is the same colour as the page background (a
  // deliberate near-invisible outline for the selected route's own bold
  // blue line) — reused for an UNselected route's casing, that meant its
  // only visible pixels were a thin 3.5px grey line, easily lost against
  // the heatmap. Unselected routes get their own, visibly distinct casing.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const otherCasingColor = useMemo(() => cssVar("--route-other-casing"), [themeVersion]);

  const selectedCasingId = `route-${selectedRouteId}-casing`;
  const ordered = useMemo(
    () => [...routes].sort((a, b) => Number(b.id === selectedRouteId) - Number(a.id === selectedRouteId)),
    [routes, selectedRouteId],
  );

  return (
    <>
      {ordered.map((route) => {
        const selected = route.id === selectedRouteId;
        const beforeId = selected ? CHECKPOINT_LAYER_ID : selectedCasingId;
        const geojson: GeoJSON.Feature = {
          type: "Feature",
          properties: {},
          geometry: route.geometry,
        };
        return (
          <Source key={route.id} id={`route-${route.id}`} type="geojson" data={geojson}>
            <Layer
              id={`route-${route.id}-casing`}
              type="line"
              beforeId={beforeId}
              layout={{ "line-cap": "round", "line-join": "round" }}
              paint={{
                "line-color": selected ? casingColor : otherCasingColor,
                "line-width": selected ? 11 : 7,
              }}
            />
            <Layer
              id={`route-${route.id}-line`}
              type="line"
              beforeId={beforeId}
              layout={{ "line-cap": "round", "line-join": "round" }}
              paint={{
                "line-color": selected ? accentColor : otherColor,
                "line-width": selected ? 6 : 4.5,
              }}
            />
          </Source>
        );
      })}
    </>
  );
}
