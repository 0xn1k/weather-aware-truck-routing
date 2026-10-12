import { useEffect, useState } from "react";
import { RoutePin } from "@/features/map/RoutePin";
import { CheckCircleIcon } from "@/lib/icons";
import { prefersReducedMotion } from "@/lib/motion";

// Loosely follows the real backend pipeline order (backend/README.md
// Section 2.1: routing -> sampling -> weather -> risk -> ranking) — there's
// no real progress signal from a single blocking HTTP request, so this is
// a timed simulation, not literal status. It only needs to feel honest
// about ORDER, not report true completion of each stage.
const STEPS = [
  "Finding routes",
  "Fetching coordinates",
  "Mapping checkpoints",
  "Checking weather along the corridor",
  "Plotting the safest path",
];
const STEP_MS = 900;

export function PlanningProgress() {
  const [stepIndex, setStepIndex] = useState(0);
  const reducedMotion = prefersReducedMotion();

  useEffect(() => {
    // A real request can finish faster or slower than this simulation —
    // reduced motion gets a single static line instead of a sequence that
    // might end up racing ahead of or lagging behind the actual response.
    if (reducedMotion) return;
    const timer = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
    }, STEP_MS);
    return () => clearInterval(timer);
  }, [reducedMotion]);

  return (
    // Sized and centred to match the empty state it replaces (App.tsx) —
    // this is a "something is happening" moment, not a small aside, so it
    // gets the same visual weight.
    <div
      role="status"
      aria-busy="true"
      aria-label="Finding the safest route"
      className="flex min-h-[460px] flex-col items-center justify-center gap-8 rounded-[20px] px-6 py-16"
      style={{ border: "1px solid var(--line)" }}
    >
      <div className="flex w-full max-w-xs items-center justify-center gap-3" aria-hidden="true">
        <RoutePin label="A" fill="var(--ink)" ink="var(--bg)" title="Start" size={26} />
        <div className="relative h-0.5 w-full max-w-[180px] flex-1 overflow-hidden rounded-full">
          <div className="absolute inset-0" style={{ borderTop: "2px dashed var(--line)" }} />
          {!reducedMotion && (
            <span
              className="absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full"
              style={{ background: "var(--accent)", animation: "corridor-scan 1.8s ease-in-out infinite" }}
            />
          )}
        </div>
        <RoutePin label="B" fill="var(--accent)" ink="var(--on-accent)" title="Destination" size={26} />
      </div>

      <div className="text-center">
        <div className="text-[18px] font-bold" style={{ color: "var(--ink)" }}>
          Finding the safest route
        </div>
        <ol className="m-0 mt-4 flex list-none flex-col items-start gap-2.5 p-0 text-left text-[13.5px]">
          {STEPS.map((label, i) => {
            const done = i < stepIndex;
            const active = i === stepIndex;
            return (
              <li
                key={label}
                className="flex items-center gap-2.5 transition-opacity duration-300"
                style={{
                  color: active ? "var(--accent)" : "var(--muted)",
                  fontWeight: active ? 600 : 400,
                  opacity: i > stepIndex ? 0.5 : 1,
                }}
              >
                {done ? (
                  <CheckCircleIcon size={16} style={{ color: "var(--accent)", flexShrink: 0 }} />
                ) : (
                  <span
                    className={`h-2 w-2 flex-none rounded-full ${active ? "animate-pulse" : ""}`}
                    style={{ background: active ? "var(--accent)" : "var(--line)" }}
                  />
                )}
                {label}
              </li>
            );
          })}
        </ol>
      </div>

      <style>{`
        @keyframes corridor-scan {
          0% { left: 0%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { left: 100%; opacity: 0; }
        }
      `}</style>
    </div>
  );
}
