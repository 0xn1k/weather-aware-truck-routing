import { useState } from "react";
import type { IntervalMiles, PlaceInput } from "@/api/types";
import { IntervalSelector } from "./IntervalSelector";
import { PlaceAutocomplete } from "./PlaceAutocomplete";
import { isTripFormValid, validateTripForm, type TripFormValues } from "./validation";

// A small safety margin under the routing provider's actual cap (1,500,000
// m = 932.06 mi, providers/routing/valhalla.py's
// VALHALLA_MAX_DISTANCE_ERROR_CODE) — the From/To browse and search lists
// only ever offer a pair the backend can actually route, instead of
// letting the user pick one and then showing them a rejection. An earlier,
// tighter cutoff (900) excluded Chicago-Denver (918 mi haversine) from its
// own dropdown despite that pair routing successfully — the cap applies to
// the straight-line distance between the two points, not the (longer)
// driven route, so there's no reason to leave much headroom here.
const MAX_TRIP_DISTANCE_MI = 925;

export interface TripSubmitValues {
  origin: PlaceInput;
  destination: PlaceInput;
  departureTimeIso: string;
  loadWeightLb: number;
  intervalMiles: IntervalMiles;
}

/** A prefill request from outside the form (e.g. "Try an example"). `token`
 * must change on every request, even if the values are identical to the
 * last one, so the effect below re-applies them. */
export interface TripFormPrefill {
  values: TripSubmitValues;
  token: number;
}

interface TripFormProps {
  onSubmit: (values: TripSubmitValues) => void;
  isSubmitting: boolean;
  prefill?: TripFormPrefill | null;
}

/** Inverse of `new Date(local).toISOString()` — turns a UTC ISO string back
 * into the local "YYYY-MM-DDTHH:mm" a datetime-local input expects. */
function isoToLocalDatetimeInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultDepartureLocal(): string {
  // .toISOString() is always UTC — feeding that straight into a
  // datetime-local input (which expects LOCAL wall-clock digits, no
  // timezone conversion) silently shifts the shown time by the viewer's
  // UTC offset. In a positive-offset zone (e.g. IST, UTC+5:30) that turns
  // "6 hours from now" into "roughly now, rounded to the hour" — often
  // already in the past by the time the user finishes filling the form,
  // even though the field displays what looks like a future time.
  // isoToLocalDatetimeInput does the conversion correctly via the Date
  // object's local getters.
  const in6Hours = new Date(Date.now() + 6 * 60 * 60 * 1000);
  in6Hours.setMinutes(0, 0, 0);
  return isoToLocalDatetimeInput(in6Hours.toISOString());
}

export function TripForm({ onSubmit, isSubmitting, prefill }: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>({
    origin: null,
    destination: null,
    departureTime: defaultDepartureLocal(),
    loadWeightLb: "42,000",
    intervalMiles: 50,
  });
  const [submitted, setSubmitted] = useState(false);

  // Applying `prefill` in a useEffect runs one render too late: the
  // key-based remount below (to reset PlaceAutocomplete's own internal
  // text state) happens in THIS render, so it would capture the still-old
  // `values.origin`/`destination` and only catch up on the NEXT prefill.
  // This is React's documented "adjust state during rendering" escape
  // hatch instead — it updates `values` synchronously, before this
  // render's JSX (including the keyed PlaceAutocompletes) is produced, so
  // the remount sees the new value immediately, not one click behind.
  const [appliedToken, setAppliedToken] = useState(prefill?.token);
  if (prefill && prefill.token !== appliedToken) {
    setAppliedToken(prefill.token);
    setValues({
      origin: prefill.values.origin,
      destination: prefill.values.destination,
      departureTime: isoToLocalDatetimeInput(prefill.values.departureTimeIso),
      loadWeightLb: prefill.values.loadWeightLb.toLocaleString(),
      intervalMiles: prefill.values.intervalMiles,
    });
    setSubmitted(false);
  }

  const errors = validateTripForm(values);
  const showErrors = submitted;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (!isTripFormValid(errors) || !values.origin || !values.destination) return;
    onSubmit({
      origin: values.origin,
      destination: values.destination,
      departureTimeIso: new Date(values.departureTime).toISOString(),
      loadWeightLb: Number(values.loadWeightLb.replace(/,/g, "")),
      intervalMiles: values.intervalMiles,
    });
  }

  return (
    <form aria-label="Trip details form" onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        <PlaceAutocomplete
          // Remount on prefill: PlaceAutocomplete owns its own `query`
          // text state, initialized once from `value?.label` on mount —
          // it never re-syncs if `value` changes later (e.g. from
          // TripForm's prefill effect). A key change forces a clean
          // remount instead, which re-initializes correctly. Normal
          // typing never changes `prefill?.token`, so this doesn't
          // interfere with ordinary use.
          key={`from-${prefill?.token ?? "initial"}`}
          id="trip-from"
          label="From"
          value={values.origin}
          onChange={(place) => setValues((v) => ({ ...v, origin: place }))}
          error={showErrors ? errors.origin : undefined}
          dotColor="var(--accent)"
          anchor={values.destination}
          maxDistanceMi={MAX_TRIP_DISTANCE_MI}
          placeholder="e.g. Chicago, IL"
        />
        <PlaceAutocomplete
          key={`to-${prefill?.token ?? "initial"}`}
          id="trip-to"
          label="To"
          value={values.destination}
          onChange={(place) => setValues((v) => ({ ...v, destination: place }))}
          error={showErrors ? errors.destination : undefined}
          dotColor="var(--risk-3)"
          anchor={values.origin}
          maxDistanceMi={MAX_TRIP_DISTANCE_MI}
          placeholder="e.g. Denver, CO"
        />
      </div>

      <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: "var(--ink)" }}>
        Departure{" "}
        <span className="font-normal" style={{ color: "var(--muted)" }}>
          your local time
        </span>
        <input
          type="datetime-local"
          value={values.departureTime}
          aria-invalid={Boolean(showErrors && errors.departureTime)}
          aria-describedby={showErrors && errors.departureTime ? "departure-err" : undefined}
          onChange={(e) => setValues((v) => ({ ...v, departureTime: e.target.value }))}
          className="h-11 w-full rounded-[10px] px-3 text-[15px] outline-none"
          style={{
            border: `${showErrors && errors.departureTime ? 2 : 1}px solid ${
              showErrors && errors.departureTime ? "var(--bad)" : "var(--input-border)"
            }`,
            background: "var(--input-bg)",
            color: "var(--ink)",
          }}
        />
        {showErrors && errors.departureTime && (
          <span id="departure-err" className="text-[13px] font-medium" style={{ color: "var(--bad)" }}>
            {errors.departureTime}
          </span>
        )}
      </label>

      <div className="flex flex-wrap gap-3">
        <label
          className="flex min-w-[130px] flex-1 flex-col gap-2 text-sm font-semibold"
          style={{ color: "var(--ink)" }}
        >
          Load weight{" "}
          <span className="font-normal" style={{ color: "var(--muted)" }}>
            pounds, cargo only
          </span>
          <input
            type="text"
            inputMode="numeric"
            value={values.loadWeightLb}
            aria-invalid={Boolean(showErrors && errors.loadWeightLb)}
            aria-describedby={showErrors && errors.loadWeightLb ? "load-err" : undefined}
            onChange={(e) => setValues((v) => ({ ...v, loadWeightLb: e.target.value }))}
            className="h-11 w-full rounded-[10px] px-3.5 text-[15px] outline-none"
            style={{
              fontFamily: "'Geist Mono', monospace",
              border: `${showErrors && errors.loadWeightLb ? 2 : 1}px solid ${
                showErrors && errors.loadWeightLb ? "var(--bad)" : "var(--input-border)"
              }`,
              background: "var(--input-bg)",
              color: "var(--ink)",
            }}
          />
          {showErrors && errors.loadWeightLb && (
            <span id="load-err" className="text-[13px] font-medium" style={{ color: "var(--bad)" }}>
              {errors.loadWeightLb}
            </span>
          )}
        </label>

        <div className="min-w-[190px] flex-1">
          <IntervalSelector
            value={values.intervalMiles}
            onChange={(interval) => setValues((v) => ({ ...v, intervalMiles: interval }))}
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={isSubmitting || !isTripFormValid(errors)}
        className="h-12 w-full rounded-xl text-[15px] font-semibold disabled:opacity-60"
        style={{ background: "var(--btn)", color: "var(--on-btn)" }}
      >
        {isSubmitting ? "Finding the safest route…" : "Find the safest route"}
      </button>
      <p className="m-0 text-[13px] leading-relaxed" style={{ color: "var(--muted)" }}>
        Weather is checked every {values.intervalMiles} miles at the hour the truck reaches that
        point. Routes are ranked by No-travel miles, then Severe, then High, then average risk,
        then drive time.
      </p>
    </form>
  );
}
