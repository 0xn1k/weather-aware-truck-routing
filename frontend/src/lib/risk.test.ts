import { describe, expect, it } from "vitest";
import { RISK_LABELS, RISK_LEVELS, riskColorVar, riskLevelFromNumber, riskTintVar } from "./risk";

describe("RISK_LEVELS", () => {
  it("is ordered Low to No travel", () => {
    expect(RISK_LEVELS).toEqual(["low", "moderate", "high", "severe", "no_travel"]);
  });

  it("has a label for every level", () => {
    for (const level of RISK_LEVELS) {
      expect(RISK_LABELS[level]).toBeTruthy();
    }
  });
});

describe("riskColorVar / riskTintVar", () => {
  it("maps each level to its own indexed CSS variable", () => {
    expect(riskColorVar("low")).toBe("var(--risk-0)");
    expect(riskColorVar("no_travel")).toBe("var(--risk-4)");
    expect(riskTintVar("severe")).toBe("var(--risk-3-tint)");
  });
});

describe("riskLevelFromNumber", () => {
  it("maps 0-4 back to the matching level name", () => {
    expect(riskLevelFromNumber(0)).toBe("low");
    expect(riskLevelFromNumber(4)).toBe("no_travel");
  });

  it("falls back to low for an out-of-range value", () => {
    expect(riskLevelFromNumber(99)).toBe("low");
  });
});
