import type { RiskLevelName } from "@/lib/risk";

export interface PlaceInput {
  lat: number;
  lon: number;
  label: string;
}

export type IntervalMiles = 10 | 25 | 50;

export interface TripPlanRequest {
  origin: PlaceInput;
  destination: PlaceInput;
  departure_time: string; // ISO 8601 UTC
  load_weight_lb: number;
  interval_miles: IntervalMiles;
}

export interface GeoJsonLineString {
  type: "LineString";
  coordinates: [number, number][]; // [lon, lat]
}

export interface Checkpoint {
  mile: number;
  lat: number;
  lon: number;
  eta: string; // ISO 8601 UTC
  wind_mph: number;
  gust_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
  risk: RiskLevelName;
  driver: "wind" | "rain" | "snow" | "load_rule";
  segment_miles: number;
}

export interface PeakReading {
  value: number;
  mile: number;
  eta: string; // ISO 8601 UTC
}

export interface RouteSummary {
  miles_by_level: Record<RiskLevelName, number>;
  avg_risk: number;
  max_level: RiskLevelName;
  worst_checkpoint: Checkpoint;
  peak_wind: PeakReading;
  peak_rain: PeakReading;
  peak_snow: PeakReading;
}

export interface RouteResult {
  id: string;
  label: string;
  rank: number;
  geometry: GeoJsonLineString;
  distance_mi: number;
  duration_s: number;
  arrival_time: string; // ISO 8601 UTC
  summary: RouteSummary;
  checkpoints: Checkpoint[];
}

export interface TripPlan {
  plan_id: string;
  recommended_route_id: string;
  recommendation_reason: string;
  warnings: string[];
  routes: RouteResult[];
}

export interface HeatmapGrid {
  points: [number, number][]; // [lat, lon]
  risk_levels: number[][]; // [hour][point], 0-4
  wind_mph: number[][]; // [hour][point]
  rain_in_hr: number[][];
  snow_in_hr: number[][];
}

export interface Place {
  lat: number;
  lon: number;
  label: string;
  context: string;
}

export type WeatherProviderName = "fake" | "open_meteo";

export interface WeatherProviderState {
  provider: WeatherProviderName;
}

export interface ApiErrorBody {
  error: {
    code: "validation_error" | "no_route" | "provider_error" | "plan_not_found" | string;
    message: string;
    fields: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  code: string;
  fields: Record<string, unknown>;
  status: number;

  constructor(body: ApiErrorBody, status: number) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.fields = body.error.fields;
    this.status = status;
  }
}
