import { AnimatePresence, motion } from "framer-motion";
import { useSetWeatherProvider } from "@/api/hooks";
import { AlertCircleIcon, CloseIcon } from "@/lib/icons";
import { scaleFade } from "@/lib/motion";

interface TripErrorModalProps {
  message: string;
  onRetry: () => void;
  onClose: () => void;
}

// The backend's weather provider wraps every Open-Meteo failure (rate
// limit or otherwise) in a message starting exactly this way —
// providers/weather/open_meteo.py's _friendly_message(). Checking for it
// is how this modal knows to offer the dummy-weather toggle specifically,
// rather than showing that suggestion for an unrelated failure (e.g. a
// routing provider error) where switching weather providers wouldn't help
// at all.
const WEATHER_ERROR_PREFIX = "Weather service";
// _friendly_message() uses this exact wording only for an actual HTTP 429 —
// every other failure (timeout, dropped connection, 5xx) gets a different,
// generic message. Distinguishing them means the explanation below doesn't
// claim "rate limited" for what was really just a transient network blip.
const RATE_LIMIT_MARKER = "rate-limited";

export function TripErrorModal({ message, onRetry, onClose }: TripErrorModalProps) {
  const setProvider = useSetWeatherProvider();
  const isWeatherError = message.startsWith(WEATHER_ERROR_PREFIX);
  const isRateLimit = message.includes(RATE_LIMIT_MARKER);

  function switchToDummyAndRetry() {
    setProvider.mutate("fake", { onSuccess: onRetry });
  }

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: "rgba(0,0,0,0.5)" }}
        onClick={onClose}
      >
        <motion.div
          variants={scaleFade}
          initial="hidden"
          animate="visible"
          exit="hidden"
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-md rounded-[20px] p-6"
          style={{ background: "var(--surface)", boxShadow: "var(--shadow)" }}
          role="alertdialog"
          aria-modal="true"
          aria-label="Something went wrong"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="flex-none" style={{ color: "var(--risk-2)" }}>
                <AlertCircleIcon size={24} />
              </span>
              <div>
                <h2 className="m-0 text-lg font-bold" style={{ color: "var(--ink)" }}>
                  Something went wrong
                </h2>
                <p className="m-0 mt-1.5 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                  {message}
                </p>
              </div>
            </div>
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              className="h-9 w-9 flex-none rounded-[10px]"
              style={{ border: "1px solid var(--line)", color: "var(--ink)" }}
            >
              <CloseIcon className="mx-auto" size={16} />
            </button>
          </div>

          {isWeatherError && (
            <div
              className="mt-4 rounded-xl p-4 text-sm leading-relaxed"
              style={{ background: "var(--accent-tint)", color: "var(--ink)" }}
            >
              {isRateLimit ? (
                <>
                  This happens when the live weather service (Open-Meteo) hits its
                  free-tier rate limit — it resets on its own after a while.
                </>
              ) : (
                <>
                  This happens when the live weather service (Open-Meteo) doesn't
                  respond in time — a brief network hiccup, not a quota limit. It
                  usually works again on the next try.
                </>
              )}{" "}
              In the meantime, you can switch to <b>dummy weather</b>: deterministic
              synthetic data, generated locally, no external calls, so it never hits
              this problem. Routing and geocoding still use the real services — only
              the weather numbers are synthetic.
            </div>
          )}

          <div className="mt-5 flex flex-col gap-2">
            {isWeatherError && (
              <button
                type="button"
                onClick={switchToDummyAndRetry}
                disabled={setProvider.isPending}
                className="h-11 w-full rounded-[10px] text-sm font-semibold disabled:opacity-60"
                style={{ background: "var(--btn)", color: "var(--on-btn)" }}
              >
                {setProvider.isPending ? "Switching…" : "Switch to dummy weather & retry"}
              </button>
            )}
            <button
              type="button"
              onClick={onRetry}
              className="h-11 w-full rounded-[10px] text-sm font-semibold"
              style={{
                border: "1px solid var(--line)",
                color: "var(--ink)",
                background: "var(--surface)",
              }}
            >
              Try again
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
