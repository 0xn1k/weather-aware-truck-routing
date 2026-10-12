import type { IntervalMiles, PlaceInput } from "@/api/types";

export interface TripFormValues {
  origin: PlaceInput | null;
  destination: PlaceInput | null;
  departureTime: string; // datetime-local value
  loadWeightLb: string; // raw text input, parsed on validate
  intervalMiles: IntervalMiles;
}

export interface TripFormErrors {
  origin?: string;
  destination?: string;
  departureTime?: string;
  loadWeightLb?: string;
}

const MAX_FORECAST_DAYS = 16;
const MIN_LOAD_LB = 1;
const MAX_LOAD_LB = 80_000;

export function validateTripForm(values: TripFormValues): TripFormErrors {
  const errors: TripFormErrors = {};

  if (!values.origin) errors.origin = "Choose a place from the suggestions.";
  if (!values.destination) errors.destination = "Choose a place from the suggestions.";

  if (
    values.origin &&
    values.destination &&
    values.origin.lat === values.destination.lat &&
    values.origin.lon === values.destination.lon
  ) {
    errors.destination = "From and To can't be the same place.";
  }

  if (!values.departureTime) {
    errors.departureTime = "Enter a departure date and time.";
  } else {
    const departure = new Date(values.departureTime);
    const now = new Date();
    const maxDate = new Date(now.getTime() + MAX_FORECAST_DAYS * 24 * 60 * 60 * 1000);
    if (departure < now) {
      errors.departureTime = "Departure time cannot be in the past.";
    } else if (departure > maxDate) {
      errors.departureTime = `Departure must be within the ${MAX_FORECAST_DAYS}-day forecast window.`;
    }
  }

  const load = Number(values.loadWeightLb.replace(/,/g, ""));
  if (!values.loadWeightLb || Number.isNaN(load)) {
    errors.loadWeightLb = `Enter a load between ${MIN_LOAD_LB} and ${MAX_LOAD_LB.toLocaleString()} lb.`;
  } else if (load < MIN_LOAD_LB || load > MAX_LOAD_LB) {
    errors.loadWeightLb = `Enter a load between ${MIN_LOAD_LB} and ${MAX_LOAD_LB.toLocaleString()} lb.`;
  }

  return errors;
}

export function isTripFormValid(errors: TripFormErrors): boolean {
  return Object.keys(errors).length === 0;
}
