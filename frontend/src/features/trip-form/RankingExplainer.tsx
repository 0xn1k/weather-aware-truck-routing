import { SectionHeader } from "@/lib/SectionHeader";

const RULES = [
  "Fewest No-travel miles",
  "Fewest Severe miles",
  "Fewest High miles",
  "Lowest average risk",
  "Shortest drive time",
];

export function RankingExplainer() {
  return (
    <div>
      <SectionHeader>How routes are ranked</SectionHeader>
      <ol className="m-0 mt-3 list-decimal pl-5 text-[13.5px] leading-[1.8]" style={{ color: "var(--ink)" }}>
        {RULES.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ol>
      <p className="m-0 mt-2 text-[13px] leading-snug" style={{ color: "var(--muted)" }}>
        Weather is read for the hour the truck reaches each checkpoint, not the departure time.
      </p>
    </div>
  );
}
