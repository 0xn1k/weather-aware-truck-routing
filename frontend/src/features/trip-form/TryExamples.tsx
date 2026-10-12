import { SectionHeader } from "@/lib/SectionHeader";
import type { TripSubmitValues } from "./TripForm";

const EXAMPLES: { label: string; load: string; note: string; values: TripSubmitValues }[] = [
  {
    label: "Chicago → Denver",
    load: "42,000 lb",
    note: "storm on I-80",
    values: {
      origin: { lat: 41.8781, lon: -87.6298, label: "Chicago, IL" },
      destination: { lat: 39.7392, lon: -104.9903, label: "Denver, CO" },
      departureTimeIso: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
      loadWeightLb: 42_000,
      intervalMiles: 25,
    },
  },
  {
    label: "Dallas → Oklahoma City",
    load: "30,000 lb",
    note: "short trip",
    values: {
      origin: { lat: 32.7767, lon: -96.797, label: "Dallas, TX" },
      destination: { lat: 35.4676, lon: -97.5164, label: "Oklahoma City, OK" },
      departureTimeIso: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
      loadWeightLb: 30_000,
      intervalMiles: 10,
    },
  },
  {
    label: "Salt Lake City → Denver",
    load: "44,000 lb",
    note: "mountain snow",
    values: {
      origin: { lat: 40.7608, lon: -111.891, label: "Salt Lake City, UT" },
      destination: { lat: 39.7392, lon: -104.9903, label: "Denver, CO" },
      departureTimeIso: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
      loadWeightLb: 44_000,
      intervalMiles: 25,
    },
  },
];

interface TryExamplesProps {
  onSelect: (values: TripSubmitValues) => void;
}

export function TryExamples({ onSelect }: TryExamplesProps) {
  return (
    <div>
      <SectionHeader>Try an example</SectionHeader>
      <div className="mt-3.5 flex flex-col gap-2.5">
        {EXAMPLES.map((example) => (
          <button
            key={example.label}
            type="button"
            onClick={() => onSelect(example.values)}
            className="rounded-xl px-3.5 py-3 text-left text-sm"
            style={{ border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          >
            {example.label} · <b style={{ color: "var(--accent)" }}>{example.load}</b>{" "}
            <span style={{ color: "var(--muted)" }}>· {example.note}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
