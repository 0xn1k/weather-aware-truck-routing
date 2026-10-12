import { describe, expect, it } from "vitest";
import { formatDuration, formatLoad, formatMiles } from "./format";

describe("formatMiles", () => {
  it("rounds and adds a thousands separator", () => {
    expect(formatMiles(1012.4)).toBe("1,012 mi");
  });
});

describe("formatDuration", () => {
  it("shows minutes only under an hour", () => {
    expect(formatDuration(45 * 60)).toBe("45 min");
  });

  it("shows hours only on an exact hour", () => {
    expect(formatDuration(3 * 3600)).toBe("3 h");
  });

  it("shows both hours and minutes otherwise", () => {
    expect(formatDuration(3 * 3600 + 30 * 60)).toBe("3 h 30 min");
  });
});

describe("formatLoad", () => {
  it("rounds and adds a thousands separator with lb suffix", () => {
    expect(formatLoad(38000)).toBe("38,000 lb");
  });
});
