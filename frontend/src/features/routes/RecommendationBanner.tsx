import { CheckCircleIcon } from "@/lib/icons";

export function RecommendationBanner({ reason }: { reason: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl p-4"
      style={{ background: "var(--rec-bg)" }}
    >
      <span className="flex-none" style={{ color: "var(--rec-ink)" }}>
        <CheckCircleIcon size={20} />
      </span>
      <div>
        <div className="text-[15px] font-bold" style={{ color: "var(--rec-ink)" }}>
          Recommended
        </div>
        <div className="mt-0.5 text-[13.5px] leading-snug" style={{ color: "var(--ink)" }}>
          {reason}
        </div>
      </div>
    </div>
  );
}
