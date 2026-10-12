export type Theme = "light" | "dark";

const STORAGE_KEY = "corridor-theme";

export function getStoredTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage can throw in a private window or with site data blocked —
    // fall through to the system preference.
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // per-viewer convenience only — fine if it silently doesn't persist.
  }
}

/** Reads a live CSS custom property (e.g. "--risk-0") from :root. Used
 * where a real resolved colour string is required (MapLibre paint
 * properties can't take `var(...)`), without duplicating the hex values
 * that already live in index.css. */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
