import { useEffect } from "react";
import { formatHourOffset } from "@/lib/format";
import { PauseIcon, PlayIcon } from "@/lib/icons";
import { prefersReducedMotion } from "@/lib/motion";
import { useUiStore } from "@/state/uiStore";

interface ForecastSliderProps {
  departureIso: string;
  truckCaption?: string;
}

export function ForecastSlider({ departureIso, truckCaption }: ForecastSliderProps) {
  const sliderHour = useUiStore((s) => s.sliderHour);
  const setSliderHour = useUiStore((s) => s.setSliderHour);
  const isPlaying = useUiStore((s) => s.isPlaying);
  const togglePlaying = useUiStore((s) => s.togglePlaying);

  useEffect(() => {
    if (!isPlaying) return;
    const stepMs = prefersReducedMotion() ? 1000 : 400;
    const timer = setInterval(() => {
      useUiStore.setState((state) => {
        const next = state.sliderHour + 1;
        return next > 48 ? { sliderHour: 0 } : { sliderHour: next };
      });
    }, stepMs);
    return () => clearInterval(timer);
  }, [isPlaying]);

  return (
    <div
      className="flex items-center gap-3.5 rounded-2xl p-3"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--line)",
        boxShadow: "var(--shadow)",
      }}
    >
      <button
        type="button"
        aria-label={isPlaying ? "Pause forecast" : "Play forecast"}
        onClick={togglePlaying}
        className="flex h-11 w-11 flex-none items-center justify-center rounded-full"
        style={{ background: "var(--btn)", color: "var(--on-btn)" }}
      >
        {isPlaying ? <PauseIcon size={15} /> : <PlayIcon size={15} />}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-[13px]">
          <label htmlFor="forecast-hour" className="font-semibold" style={{ color: "var(--ink)" }}>
            Forecast{" "}
            <span style={{ fontFamily: "'Geist Mono', monospace", color: "var(--accent)" }}>
              {formatHourOffset(sliderHour, departureIso)}
            </span>
          </label>
          {truckCaption && (
            <span className="truncate" style={{ color: "var(--muted)" }}>
              {truckCaption}
            </span>
          )}
        </div>
        <input
          id="forecast-hour"
          type="range"
          min={0}
          max={48}
          step={1}
          value={sliderHour}
          onChange={(e) => setSliderHour(Number(e.target.value))}
          className="mt-1.5 w-full"
          style={{ accentColor: "var(--accent)" }}
        />
      </div>
    </div>
  );
}
