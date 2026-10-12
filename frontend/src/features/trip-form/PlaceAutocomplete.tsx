import { useEffect, useRef, useState } from "react";
import { usePlaceSearch } from "@/api/hooks";
import type { Place, PlaceInput } from "@/api/types";
import { haversineMi } from "@/lib/geo";

interface PlaceAutocompleteProps {
  id: string;
  label: string;
  value: PlaceInput | null;
  onChange: (place: PlaceInput | null) => void;
  error?: string;
  /** Small colour dot inside the field — e.g. accent blue for "From", the
   * severe-risk red for "To" — so the two endpoints read apart at a glance,
   * matching the start/end pin colours on the map. */
  dotColor?: string;
  /** The OTHER field's current value, if any — when set, every option
   * (browse list and live search alike) farther than maxDistanceMi from it
   * is filtered out, so a user can never pick a pair the routing provider
   * will reject as too far apart (backend/README.md: Valhalla's ~930 mi
   * cap). */
  anchor?: PlaceInput | null;
  maxDistanceMi?: number;
  placeholder?: string;
}

// Browsable on focus/click — major US metros, alphabetical, so either field
// (empty or already filled) always has a quick pick list for testing
// without typing + waiting on a real geocode round trip.
const DEFAULT_PLACES: Place[] = [
  { lat: 35.0844, lon: -106.6504, label: "Albuquerque, NM", context: "New Mexico, United States" },
  { lat: 35.222, lon: -101.8313, label: "Amarillo, TX", context: "Texas, United States" },
  { lat: 33.749, lon: -84.388, label: "Atlanta, GA", context: "Georgia, United States" },
  { lat: 30.2672, lon: -97.7431, label: "Austin, TX", context: "Texas, United States" },
  { lat: 35.3733, lon: -119.0187, label: "Bakersfield, CA", context: "California, United States" },
  { lat: 39.2904, lon: -76.6122, label: "Baltimore, MD", context: "Maryland, United States" },
  { lat: 45.7833, lon: -108.5007, label: "Billings, MT", context: "Montana, United States" },
  { lat: 33.5186, lon: -86.8104, label: "Birmingham, AL", context: "Alabama, United States" },
  { lat: 43.615, lon: -116.2023, label: "Boise, ID", context: "Idaho, United States" },
  { lat: 42.3601, lon: -71.0589, label: "Boston, MA", context: "Massachusetts, United States" },
  { lat: 35.2271, lon: -80.8431, label: "Charlotte, NC", context: "North Carolina, United States" },
  { lat: 41.8781, lon: -87.6298, label: "Chicago, IL", context: "Illinois, United States" },
  { lat: 39.1031, lon: -84.512, label: "Cincinnati, OH", context: "Ohio, United States" },
  { lat: 41.4993, lon: -81.6944, label: "Cleveland, OH", context: "Ohio, United States" },
  { lat: 39.9612, lon: -82.9988, label: "Columbus, OH", context: "Ohio, United States" },
  { lat: 32.7767, lon: -96.797, label: "Dallas, TX", context: "Texas, United States" },
  { lat: 39.7392, lon: -104.9903, label: "Denver, CO", context: "Colorado, United States" },
  { lat: 41.5868, lon: -93.625, label: "Des Moines, IA", context: "Iowa, United States" },
  { lat: 42.3314, lon: -83.0458, label: "Detroit, MI", context: "Michigan, United States" },
  { lat: 31.7619, lon: -106.485, label: "El Paso, TX", context: "Texas, United States" },
  { lat: 46.8772, lon: -96.7898, label: "Fargo, ND", context: "North Dakota, United States" },
  { lat: 29.7604, lon: -95.3698, label: "Houston, TX", context: "Texas, United States" },
  { lat: 39.7684, lon: -86.1581, label: "Indianapolis, IN", context: "Indiana, United States" },
  { lat: 30.3322, lon: -81.6557, label: "Jacksonville, FL", context: "Florida, United States" },
  { lat: 39.0997, lon: -94.5786, label: "Kansas City, MO", context: "Missouri, United States" },
  { lat: 36.1699, lon: -115.1398, label: "Las Vegas, NV", context: "Nevada, United States" },
  { lat: 34.7465, lon: -92.2896, label: "Little Rock, AR", context: "Arkansas, United States" },
  { lat: 34.0522, lon: -118.2437, label: "Los Angeles, CA", context: "California, United States" },
  { lat: 38.2527, lon: -85.7585, label: "Louisville, KY", context: "Kentucky, United States" },
  { lat: 35.1495, lon: -90.049, label: "Memphis, TN", context: "Tennessee, United States" },
  { lat: 25.7617, lon: -80.1918, label: "Miami, FL", context: "Florida, United States" },
  { lat: 43.0389, lon: -87.9065, label: "Milwaukee, WI", context: "Wisconsin, United States" },
  { lat: 44.9778, lon: -93.265, label: "Minneapolis, MN", context: "Minnesota, United States" },
  { lat: 36.1627, lon: -86.7816, label: "Nashville, TN", context: "Tennessee, United States" },
  { lat: 29.9511, lon: -90.0715, label: "New Orleans, LA", context: "Louisiana, United States" },
  { lat: 40.7128, lon: -74.006, label: "New York, NY", context: "New York, United States" },
  { lat: 35.4676, lon: -97.5164, label: "Oklahoma City, OK", context: "Oklahoma, United States" },
  { lat: 41.2565, lon: -95.9345, label: "Omaha, NE", context: "Nebraska, United States" },
  { lat: 39.9526, lon: -75.1652, label: "Philadelphia, PA", context: "Pennsylvania, United States" },
  { lat: 33.4484, lon: -112.074, label: "Phoenix, AZ", context: "Arizona, United States" },
  { lat: 40.4406, lon: -79.9959, label: "Pittsburgh, PA", context: "Pennsylvania, United States" },
  { lat: 45.5152, lon: -122.6784, label: "Portland, OR", context: "Oregon, United States" },
  { lat: 35.7796, lon: -78.6382, label: "Raleigh, NC", context: "North Carolina, United States" },
  { lat: 39.5296, lon: -119.8138, label: "Reno, NV", context: "Nevada, United States" },
  { lat: 38.5816, lon: -121.4944, label: "Sacramento, CA", context: "California, United States" },
  { lat: 40.7608, lon: -111.891, label: "Salt Lake City, UT", context: "Utah, United States" },
  { lat: 29.4241, lon: -98.4936, label: "San Antonio, TX", context: "Texas, United States" },
  { lat: 32.7157, lon: -117.1611, label: "San Diego, CA", context: "California, United States" },
  { lat: 37.7749, lon: -122.4194, label: "San Francisco, CA", context: "California, United States" },
  { lat: 47.6062, lon: -122.3321, label: "Seattle, WA", context: "Washington, United States" },
  { lat: 47.6588, lon: -117.426, label: "Spokane, WA", context: "Washington, United States" },
  { lat: 38.627, lon: -90.1994, label: "St. Louis, MO", context: "Missouri, United States" },
  { lat: 27.9506, lon: -82.4572, label: "Tampa, FL", context: "Florida, United States" },
  { lat: 32.2226, lon: -110.9747, label: "Tucson, AZ", context: "Arizona, United States" },
  { lat: 36.154, lon: -95.9928, label: "Tulsa, OK", context: "Oklahoma, United States" },
  { lat: 37.6872, lon: -97.3301, label: "Wichita, KS", context: "Kansas, United States" },
];

export function PlaceAutocomplete({
  id,
  label,
  value,
  onChange,
  error,
  dotColor,
  anchor,
  maxDistanceMi,
  placeholder,
}: PlaceAutocompleteProps) {
  const [query, setQuery] = useState(value?.label ?? "");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  // The label of whatever was last actually confirmed (a click/Enter on an
  // option) — not just whatever happens to be in the text box. Comparing
  // against this (rather than against the `value` prop, which this
  // component itself clears to null on every keystroke) is what lets a
  // field that's already filled still open the browse list on a plain
  // click, while a field someone is actively editing still searches.
  const confirmedLabelRef = useRef(value?.label ?? "");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Skip the search when the current text already matches a confirmed
  // selection — e.g. right after picking a suggestion, or when a place is
  // set from outside (TripForm's "Try an example" prefill). Without this,
  // every prefill or selection re-searches text we already resolved,
  // wasting a geocode call for nothing new.
  const searchEnabled = !(value && value.label === debouncedQuery);
  const { data: suggestions = [], isFetching } = usePlaceSearch(debouncedQuery, searchEnabled);

  // Browse mode: the field is empty, or still shows exactly what was last
  // confirmed (nothing typed since). Either way there's no fresh search
  // text to run, so show the full pick list instead of an empty dropdown.
  const isBrowsing = query.trim().length === 0 || query === confirmedLabelRef.current;
  const showResults = !isBrowsing && debouncedQuery.trim().length > 1;
  const withinRange = (place: Place) =>
    !anchor || !maxDistanceMi || haversineMi(place, anchor) <= maxDistanceMi;
  const activeList = (isBrowsing ? DEFAULT_PLACES : suggestions).filter(withinRange);
  const dropdownVisible = open && (isBrowsing || showResults);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function selectPlace(place: Place) {
    onChange({ lat: place.lat, lon: place.lon, label: place.label });
    confirmedLabelRef.current = place.label;
    setQuery(place.label);
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (!dropdownVisible || activeList.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, activeList.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectPlace(activeList[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const borderColor = error ? "var(--bad)" : "var(--input-border)";

  return (
    <div ref={containerRef} className="relative flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
        {label}
      </label>
      <div className="relative">
        {dotColor && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full"
            style={{ background: dotColor }}
          />
        )}
        <input
          id={id}
          type="text"
          value={query}
          placeholder={placeholder}
          // "off" suppresses the browser's own "previously typed in this
          // field" suggestion list (a plain unstyled dropdown that can
          // layer on top of ours). That's a different feature from
          // password-manager autofill — which ignores "off" and needs the
          // "new-password" workaround instead — so plain "off" is correct
          // and sufficient here.
          autoComplete="off"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-err` : undefined}
          aria-expanded={open}
          aria-autocomplete="list"
          role="combobox"
          onChange={(e) => {
            setQuery(e.target.value);
            onChange(null);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          className={`h-11 w-full rounded-[10px] ${dotColor ? "pl-9" : "px-3.5"} pr-3.5 text-[15px] outline-none`}
          style={{
            border: `${error ? 2 : 1}px solid ${borderColor}`,
            background: "var(--input-bg)",
            color: "var(--ink)",
          }}
        />
      </div>
      {error && (
        <div id={`${id}-err`} className="text-[13px] font-medium" style={{ color: "var(--bad)" }}>
          {error}
        </div>
      )}
      {dropdownVisible && (
        <div
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute top-full z-10 mt-1 max-h-80 w-full overflow-y-auto rounded-xl"
          style={{
            border: "1px solid var(--line)",
            boxShadow: "var(--shadow)",
            background: "var(--surface)",
          }}
        >
          {!isBrowsing && isFetching && suggestions.length === 0 && (
            <div className="px-3.5 py-2.5 text-sm" style={{ color: "var(--muted)" }}>
              Searching…
            </div>
          )}
          {!isBrowsing && !isFetching && suggestions.length > 0 && activeList.length === 0 && (
            <div className="px-3.5 py-2.5 text-sm" style={{ color: "var(--muted)" }}>
              No matches within {maxDistanceMi} mi of {anchor?.label}.
            </div>
          )}
          {!isBrowsing && !isFetching && suggestions.length === 0 && (
            <div className="px-3.5 py-2.5 text-sm" style={{ color: "var(--muted)" }}>
              No places found.
            </div>
          )}
          {activeList.map((place, index) => (
            <div
              key={`${place.lat}-${place.lon}-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={() => selectPlace(place)}
              className="flex cursor-pointer items-start gap-2 px-3.5 py-2.5"
              style={{
                background: index === activeIndex ? "var(--accent-tint)" : undefined,
                borderTop: index > 0 ? "1px solid var(--line-2)" : undefined,
              }}
            >
              <PinIcon className="mt-0.5 flex-none" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold" style={{ color: "var(--ink)" }}>
                  {place.label}
                </div>
                {place.context && (
                  <div className="truncate text-xs" style={{ color: "var(--muted)" }}>
                    {place.context}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PinIcon({ className }: { className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
      style={{ color: "var(--risk-3)" }}
    >
      <path
        d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"
        fill="currentColor"
      />
      <circle cx="12" cy="9" r="2.5" fill="var(--surface)" />
    </svg>
  );
}
