import { describe, expect, it } from "vitest";
import { isTripFormValid, validateTripForm, type TripFormValues } from "./validation";

const PLACE = { lat: 41.8781, lon: -87.6298, label: "Chicago, IL" };
const OTHER_PLACE = { lat: 39.7392, lon: -104.9903, label: "Denver, CO" };

function baseValues(overrides: Partial<TripFormValues> = {}): TripFormValues {
  const in6Hours = new Date(Date.now() + 6 * 60 * 60 * 1000);
  return {
    origin: PLACE,
    destination: OTHER_PLACE,
    departureTime: in6Hours.toISOString().slice(0, 16),
    loadWeightLb: "42,000",
    intervalMiles: 25,
    ...overrides,
  };
}

describe("validateTripForm", () => {
  it("is valid for complete, in-range values", () => {
    const errors = validateTripForm(baseValues());
    expect(isTripFormValid(errors)).toBe(true);
  });

  it("requires origin and destination", () => {
    const errors = validateTripForm(baseValues({ origin: null, destination: null }));
    expect(errors.origin).toBeTruthy();
    expect(errors.destination).toBeTruthy();
  });

  it("rejects a departure time in the past", () => {
    const anHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString().slice(0, 16);
    const errors = validateTripForm(baseValues({ departureTime: anHourAgo }));
    expect(errors.departureTime).toMatch(/past/);
  });

  it("rejects a departure beyond the 16-day forecast window", () => {
    const in17Days = new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16);
    const errors = validateTripForm(baseValues({ departureTime: in17Days }));
    expect(errors.departureTime).toMatch(/16-day/);
  });

  it("rejects a load of 0 lb", () => {
    const errors = validateTripForm(baseValues({ loadWeightLb: "0" }));
    expect(errors.loadWeightLb).toBeTruthy();
  });

  it("accepts a load of exactly 80,000 lb", () => {
    const errors = validateTripForm(baseValues({ loadWeightLb: "80,000" }));
    expect(errors.loadWeightLb).toBeUndefined();
  });

  it("rejects a load over 80,000 lb", () => {
    const errors = validateTripForm(baseValues({ loadWeightLb: "80,001" }));
    expect(errors.loadWeightLb).toBeTruthy();
  });

  it("rejects origin and destination being the same place", () => {
    const errors = validateTripForm(baseValues({ destination: PLACE }));
    expect(errors.destination).toMatch(/same place/);
  });

  it("allows two different places with the same label but different coordinates", () => {
    // e.g. two distinct "Springfield" results from a search — same text,
    // not actually the same point, so this must NOT be treated as a dupe.
    const sameLabelDifferentPlace = { ...PLACE, lat: PLACE.lat + 1 };
    const errors = validateTripForm(baseValues({ destination: sameLabelDifferentPlace }));
    expect(errors.destination).toBeUndefined();
  });
});
