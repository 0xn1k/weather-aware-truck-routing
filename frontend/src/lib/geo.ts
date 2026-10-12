const EARTH_RADIUS_MI = 3958.7613;

/** Great-circle distance in miles — mirrors backend/core/geo.py's
 * haversine(), used here only to keep the From/To browse list from ever
 * offering a pair that exceeds the routing provider's ~930 mi cap
 * (PlaceAutocomplete's maxDistanceMi prop). */
export function haversineMi(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.sqrt(h));
}
