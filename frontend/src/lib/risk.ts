import { cssVar } from "./theme";

export type RiskLevelName = "low" | "moderate" | "high" | "severe" | "no_travel";

/** The one ordered list every risk-related lookup in the app derives from. */
export const RISK_LEVELS: RiskLevelName[] = ["low", "moderate", "high", "severe", "no_travel"];

export const RISK_LABELS: Record<RiskLevelName, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No travel",
};

function riskIndex(level: RiskLevelName): number {
  return RISK_LEVELS.indexOf(level);
}

/** CSS var reference for inline styles / Tailwind arbitrary values. */
export function riskColorVar(level: RiskLevelName): string {
  return `var(--risk-${riskIndex(level)})`;
}

export function riskTintVar(level: RiskLevelName): string {
  return `var(--risk-${riskIndex(level)}-tint)`;
}

/** Resolved hex string — needed for MapLibre paint properties, which can't
 * take a CSS var(). Reads the live theme, so it stays correct across a
 * light/dark toggle without a second copy of the colour values. */
export function riskColorResolved(level: RiskLevelName): string {
  return cssVar(`--risk-${riskIndex(level)}`);
}

export function riskLevelFromNumber(level: number): RiskLevelName {
  return RISK_LEVELS[level] ?? "low";
}
