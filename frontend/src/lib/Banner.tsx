import { AlertCircleIcon, WarningIcon } from "./icons";

export type BannerVariant = "no_travel" | "info" | "waking_up" | "error";

interface BannerProps {
  variant: BannerVariant;
  title: string;
  description?: string;
  onRetry?: () => void;
}

const VARIANT_STYLE: Record<BannerVariant, { bg: string; fg: string; role: "status" | "alert" }> = {
  no_travel: { bg: "var(--risk-4-tint)", fg: "var(--risk-4)", role: "status" },
  info: { bg: "var(--risk-0-tint)", fg: "var(--risk-0)", role: "status" },
  waking_up: { bg: "var(--chip)", fg: "var(--accent)", role: "status" },
  error: { bg: "var(--risk-2-tint)", fg: "var(--risk-2)", role: "alert" },
};

export function Banner({ variant, title, description, onRetry }: BannerProps) {
  const style = VARIANT_STYLE[variant];
  return (
    <div
      role={style.role}
      className="flex items-start gap-3 rounded-xl p-4"
      style={{ background: style.bg }}
    >
      <span className="flex-none" style={{ color: style.fg }}>
        {variant === "waking_up" && <Spinner />}
        {variant === "no_travel" && <WarningIcon size={22} />}
        {(variant === "info" || variant === "error") && <AlertCircleIcon size={22} />}
      </span>
      <div className="flex-1">
        <div className="text-[15px] font-bold" style={{ color: "var(--ink)" }}>
          {title}
        </div>
        {description && (
          <div className="mt-0.5 text-[13.5px] leading-snug" style={{ color: "var(--muted)" }}>
            {description}
          </div>
        )}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="h-11 flex-none rounded-[10px] px-4 text-sm font-semibold"
          style={{ background: "var(--btn)", color: "var(--on-btn)" }}
        >
          Try again
        </button>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" className="animate-spin">
      <circle cx="12" cy="12" r="9" fill="none" stroke="var(--line)" strokeWidth={3} />
      <path
        d="M12 3a9 9 0 0 1 9 9"
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
      />
    </svg>
  );
}

export function NoTravelBanner() {
  return (
    <Banner
      variant="no_travel"
      title="Do not travel at this departure time"
      description="Every route crosses No travel conditions. Change the departure time or the load. Routes are still ranked below."
    />
  );
}

export function FewerRoutesBanner({ count }: { count: number }) {
  return (
    <Banner
      variant="info"
      title={`Only ${count} different route${count === 1 ? "" : "s"} exist for this trip`}
      description="Any third option repeated more than 80% of a route already shown, or took over 1.5x the fastest time."
    />
  );
}

export function WakingUpBanner() {
  return (
    <Banner
      variant="waking_up"
      title="Connecting to the server…"
      description="The first request after a fresh deploy can take a moment to respond. Your trip is kept."
    />
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Banner variant="error" title="Something went wrong" description={message} onRetry={onRetry} />
  );
}
