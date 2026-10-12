import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  HeatmapGrid,
  Place,
  TripPlan,
  TripPlanRequest,
  WeatherProviderName,
  WeatherProviderState,
} from "./types";

export function useTripPlan() {
  return useMutation({
    mutationFn: (request: TripPlanRequest) =>
      apiClient.post<TripPlan>("/api/trips/plan", request),
  });
}

export function useHeatmap(planId: string | null) {
  return useQuery({
    queryKey: ["heatmap", planId],
    queryFn: () => apiClient.get<HeatmapGrid>(`/api/trips/${planId}/heatmap`),
    enabled: planId !== null,
    staleTime: 60 * 60 * 1000, // matches the backend's 60 min plan cache
  });
}

export function usePlaceSearch(query: string, enabled = true) {
  return useQuery({
    queryKey: ["geocode", query],
    queryFn: () => apiClient.get<Place[]>(`/api/geocode?q=${encodeURIComponent(query)}`),
    enabled: enabled && query.trim().length > 1,
    staleTime: 24 * 60 * 60 * 1000, // matches the backend's 24h geocode cache
  });
}

/** The backend's active weather source — toggled from the header (no
 * redeploy needed, see providers/registry.py's set_weather_provider_name).
 * It's a server-wide setting, not per-browser, so this is intentionally
 * NOT cached across page loads the way geocode/health are — always refetch
 * on mount so the toggle reflects whatever the backend is actually using
 * right now, including a switch made from a different tab. */
export function useWeatherProvider() {
  return useQuery({
    queryKey: ["weather-provider"],
    queryFn: () => apiClient.get<WeatherProviderState>("/api/weather-provider"),
    staleTime: 0,
  });
}

export function useSetWeatherProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: WeatherProviderName) =>
      apiClient.post<WeatherProviderState>("/api/weather-provider", { provider }),
    onSuccess: (data) => {
      queryClient.setQueryData(["weather-provider"], data);
    },
  });
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.get<{ status: string }>("/api/health"),
    retry: 10,
    retryDelay: 3000, // Render free tier can take ~1 min to wake from sleep
    refetchOnWindowFocus: false,
  });
}
