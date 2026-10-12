import { RISK_LEVELS, riskColorVar } from "@/lib/risk";
import type { RouteSummary } from "@/api/types";

interface RiskBarProps {
  milesByLevel: RouteSummary["miles_by_level"];
  height?: number;
}

export function RiskBar({ milesByLevel, height = 10 }: RiskBarProps) {
  const total = RISK_LEVELS.reduce((sum, level) => sum + (milesByLevel[level] ?? 0), 0) || 1;

  return (
    <div
      className="flex w-full overflow-hidden rounded-full"
      style={{ height }}
      role="img"
      aria-label="Risk along the route, by miles"
    >
      {RISK_LEVELS.map((level) => {
        const miles = milesByLevel[level] ?? 0;
        if (miles <= 0) return null;
        return (
          <div
            key={level}
            style={{ width: `${(miles / total) * 100}%`, background: riskColorVar(level) }}
            title={`${level}: ${Math.round(miles)} mi`}
          />
        );
      })}
    </div>
  );
}
