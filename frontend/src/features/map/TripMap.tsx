import { useEffect, useRef, useState } from "react";
import Map, { type MapLayerMouseEvent, type MapRef, NavigationControl } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Checkpoint, HeatmapGrid, RouteResult } from "@/api/types";
import { CloseIcon, ExpandIcon } from "@/lib/icons";
import { sortByRank } from "@/lib/routeOrder";
import { useUiStore } from "@/state/uiStore";
import { ForecastSlider } from "@/features/forecast/ForecastSlider";
import { RouteCard } from "@/features/routes/RouteCard";
import { CHECKPOINT_LAYER_ID, CheckpointLayer } from "./layers/CheckpointLayer";
import { HeatmapLayer } from "./layers/HeatmapLayer";
import { RouteLayer } from "./layers/RouteLayer";
import { TruckPositionLayer } from "./layers/TruckPositionLayer";
import { CheckpointPopup } from "./CheckpointPopup";
import { Legend } from "./Legend";
import { basemapStyleUrl } from "./mapStyle";
import { StartEndMarkers } from "./StartEndMarkers";

const LETTERS = ["A", "B", "C", "D", "E"];

interface TripMapProps {
  routes: RouteResult[];
  selectedRouteId: string;
  recommendedRouteId: string;
  departureIso: string;
  heatmapGrid?: HeatmapGrid;
  sliderHour: number;
  showHeatmap: boolean;
  originLabel?: string;
  destinationLabel?: string;
  onOpenDetails: (id: string) => void;
}

function boundsOf(routes: RouteResult[]): [[number, number], [number, number]] {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const route of routes) {
    for (const [lon, lat] of route.geometry.coordinates) {
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
    }
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

export function TripMap({
  routes,
  selectedRouteId,
  recommendedRouteId,
  departureIso,
  heatmapGrid,
  sliderHour,
  showHeatmap,
  originLabel,
  destinationLabel,
  onOpenDetails,
}: TripMapProps) {
  const theme = useUiStore((s) => s.theme);
  const mapRef = useRef<MapRef>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const selectedRoute = routes.find((r) => r.id === selectedRouteId);
  const setSelectedRouteId = useUiStore((s) => s.setSelectedRouteId);
  const rankedRoutes = sortByRank(routes);
  const selectedLetter = LETTERS[rankedRoutes.findIndex((r) => r.id === selectedRouteId)];
  const fastestId = routes.length
    ? routes.reduce((fastest, r) => (r.duration_s < fastest.duration_s ? r : fastest)).id
    : undefined;

  useEffect(() => {
    if (!isExpanded) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setIsExpanded(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isExpanded]);

  useEffect(() => {
    // Same map instance throughout — expanding/collapsing is a pure CSS
    // size change (fixed inset-0 vs the normal card), not a remount, so no
    // WebGL re-init/flicker and no reloaded tiles. MapLibre doesn't pick up
    // a container resize on its own, though, so it has to be told
    // explicitly once the new size has actually painted.
    const id = requestAnimationFrame(() => mapRef.current?.resize());
    return () => cancelAnimationFrame(id);
  }, [isExpanded]);

  useEffect(() => {
    // mapRef.current being non-null only means the ref is attached, not
    // that MapLibre has actually finished loading — calling fitBounds
    // before that is silently ignored (no error, no effect). This used to
    // go unnoticed because real weather API calls were slow enough that
    // the map always finished loading first; the near-instant fake
    // provider (providers/weather/fake.py) can return trip data before the
    // map is ready, so the race started actually losing. mapLoaded (set by
    // the <Map>'s onLoad below) is a real dependency here specifically so
    // this effect re-runs and retries once the map becomes ready, even if
    // routes arrived first.
    if (!mapLoaded || !mapRef.current) return;
    // Fit to the SELECTED route only, not every alternative — an
    // alternate/detour route can swing much wider than the one actually on
    // screen, forcing the whole camera to zoom out to include a path that
    // isn't even the focus. Re-fits on every selection change too, so
    // clicking a different route (sidebar card or the route's own line on
    // the map) re-frames around it instead of leaving the earlier framing.
    const target = selectedRoute ?? routes[0];
    if (!target) return;
    mapRef.current.fitBounds(boundsOf([target]), { padding: 56, duration: 600 });
  }, [mapLoaded, selectedRoute, routes]);

  // Both the wide casing and the narrower coloured line are clickable —
  // the casing is the easier target to actually hit with a pointer.
  const routeLayerIds = routes.flatMap((r) => [`route-${r.id}-line`, `route-${r.id}-casing`]);
  const interactiveLayerIds = selectedRoute
    ? [CHECKPOINT_LAYER_ID, ...routeLayerIds]
    : routeLayerIds;

  function handleMapClick(event: MapLayerMouseEvent) {
    const features = event.features ?? [];

    // A checkpoint sits directly on top of its own route's line, so if
    // both were hit at this point, the more specific checkpoint click wins
    // (it already belongs to the selected route — nothing to re-select).
    const checkpointFeature = features.find((f) => f.layer.id === CHECKPOINT_LAYER_ID);
    if (checkpointFeature && selectedRoute) {
      const index = checkpointFeature.properties?.index as number;
      const checkpoint = selectedRoute.checkpoints[index];
      if (checkpoint) setSelectedCheckpoint(checkpoint);
      return;
    }

    const routeFeature = features.find((f) => /^route-.+-(line|casing)$/.test(f.layer.id));
    const routeId = routeFeature ? /^route-(.+)-(line|casing)$/.exec(routeFeature.layer.id)?.[1] : undefined;
    if (routeId) setSelectedRouteId(routeId);
  }

  return (
    <div
      className={
        isExpanded
          ? "fixed inset-0 z-50 h-screen w-screen overflow-hidden"
          : "relative h-full w-full overflow-hidden rounded-[20px]"
      }
      style={isExpanded ? undefined : { border: "1px solid var(--line)" }}
    >
      <Map
        ref={mapRef}
        mapStyle={basemapStyleUrl(theme)}
        initialViewState={{ longitude: -95, latitude: 40, zoom: 4 }}
        interactiveLayerIds={interactiveLayerIds}
        onClick={handleMapClick}
        onLoad={() => setMapLoaded(true)}
        onError={(e) => console.error("[TripMap] MapLibre error:", e.error)}
        aria-label="Map of the truck routes with risk-coloured checkpoints"
      >
        <NavigationControl position="top-right" />
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          aria-label={isExpanded ? "Collapse map" : "Expand map"}
          className="absolute left-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-lg"
          style={{ background: "var(--surface)", color: "var(--ink)", boxShadow: "var(--shadow)" }}
        >
          {isExpanded ? <CloseIcon size={17} /> : <ExpandIcon size={17} />}
        </button>
        {/* CheckpointLayer must mount before RouteLayer: RouteLayer anchors
            every route's layers with beforeId={CHECKPOINT_LAYER_ID} so a
            newly-selected route's line never gets pushed above the
            checkpoint dots, and MapLibre requires that target layer to
            already exist the first time a route layer is created. */}
        {selectedRoute && <CheckpointLayer route={selectedRoute} themeVersion={theme} />}
        <RouteLayer routes={routes} selectedRouteId={selectedRouteId} themeVersion={theme} />
        {showHeatmap && heatmapGrid && (
          <HeatmapLayer
            grid={heatmapGrid}
            hour={sliderHour}
            beforeId={`route-${selectedRouteId}-casing`}
          />
        )}
        {selectedRoute && (
          <StartEndMarkers
            route={selectedRoute}
            originLabel={originLabel}
            destinationLabel={destinationLabel}
          />
        )}
        {selectedRoute && heatmapGrid && (
          <TruckPositionLayer route={selectedRoute} departureIso={departureIso} hour={sliderHour} />
        )}
        {isExpanded && showHeatmap && heatmapGrid && (
          <div className="absolute top-4 left-1/2 z-10 w-[460px] max-w-[85vw] -translate-x-1/2">
            <ForecastSlider departureIso={departureIso} />
          </div>
        )}
        {isExpanded && selectedRoute && selectedLetter && (
          <div className="absolute bottom-4 right-4 z-10 w-[380px] max-w-[90vw]">
            <RouteCard
              route={selectedRoute}
              letter={selectedLetter}
              totalRoutes={routes.length}
              isSelected
              isRecommended={selectedRoute.id === recommendedRouteId}
              isFastest={selectedRoute.id === fastestId}
              onSelect={() => setSelectedRouteId(selectedRoute.id)}
              onOpenDetails={() => onOpenDetails(selectedRoute.id)}
            />
          </div>
        )}
        {selectedCheckpoint && (
          <CheckpointPopup
            checkpoint={selectedCheckpoint}
            onClose={() => setSelectedCheckpoint(null)}
          />
        )}
      </Map>
      <Legend />
    </div>
  );
}
