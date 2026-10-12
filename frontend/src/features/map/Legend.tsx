import { RISK_LABELS, RISK_LEVELS, riskColorVar } from "@/lib/risk";

export function Legend() {
  return (
    <div
      className="absolute bottom-4 left-4 z-10 rounded-xl p-3"
      style={{ background: "var(--surface)", border: "1px solid var(--line)", boxShadow: "var(--shadow)" }}
    >
      <ol className="m-0 flex list-none flex-col gap-1.5 p-0">
        {RISK_LEVELS.map((level) => (
          <li key={level} className="flex items-center gap-2 text-xs" style={{ color: "var(--ink)" }}>
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: riskColorVar(level) }}
            />
            {RISK_LABELS[level]}
          </li>
        ))}
      </ol>
    </div>
  );
}
