import { useSetWeatherProvider, useWeatherProvider } from "@/api/hooks";

/** Header button that flips the backend between live weather (open_meteo)
 * and deterministic dummy weather (fake, providers/weather/fake.py) —
 * instantly, no env var change or redeploy. See
 * providers/registry.py's set_weather_provider_name for what this does and
 * doesn't affect: it's a server-wide switch (every tab/user hitting this
 * backend sees the same state), not per-browser, and resets to whatever
 * WEATHER_PROVIDER is set to in the environment on the next deploy. */
export function WeatherProviderToggle() {
  const { data, isLoading } = useWeatherProvider();
  const setProvider = useSetWeatherProvider();

  if (isLoading || !data) return null;

  const isLive = data.provider === "open_meteo";
  const nextProvider = isLive ? "fake" : "open_meteo";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isLive}
      onClick={() => setProvider.mutate(nextProvider)}
      disabled={setProvider.isPending}
      aria-label={`Weather source: ${isLive ? "live" : "dummy"}. Click to switch to ${
        isLive ? "dummy" : "live"
      } weather.`}
      title="Toggle between live and dummy weather data (testing only)"
      className="flex items-center gap-2 whitespace-nowrap px-1 text-[13px] font-semibold disabled:opacity-60"
      style={{ color: "var(--ink)" }}
    >
      {isLive ? "Live weather" : "Dummy weather"}
      <span
        aria-hidden="true"
        className="relative inline-flex h-6 w-11 flex-none items-center rounded-full transition-colors duration-200"
        style={{ background: isLive ? "var(--accent)" : "var(--line)" }}
      >
        <span
          className="inline-block h-[18px] w-[18px] transform rounded-full bg-white shadow transition-transform duration-200"
          style={{ transform: isLive ? "translateX(22px)" : "translateX(3px)" }}
        />
      </span>
    </button>
  );
}
