import type { IntervalMiles } from "@/api/types";

const INTERVALS: IntervalMiles[] = [10, 25, 50];

interface IntervalSelectorProps {
  value: IntervalMiles;
  onChange: (value: IntervalMiles) => void;
}

export function IntervalSelector({ value, onChange }: IntervalSelectorProps) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
        Check weather every
      </span>
      <div
        role="group"
        aria-label="Check weather every"
        className="flex gap-0.5 rounded-xl p-1"
        style={{ background: "var(--seg-bg)", border: "1px solid var(--line)" }}
      >
        {INTERVALS.map((interval) => {
          const on = interval === value;
          return (
            <button
              key={interval}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(interval)}
              className="h-9 flex-1 rounded-[9px] text-sm"
              style={{
                background: on ? "var(--seg-on)" : "transparent",
                color: on ? "var(--ink)" : "var(--muted)",
                fontWeight: on ? 700 : 500,
                boxShadow: on ? "var(--shadow)" : "none",
              }}
            >
              {interval} mi
            </button>
          );
        })}
      </div>
    </div>
  );
}
