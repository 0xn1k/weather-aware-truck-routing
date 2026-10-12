import type { Theme } from "@/lib/theme";

/** OpenFreeMap vector styles — no API key, loaded directly by the browser
 * (top-level README.md Section 2). Basemap switches with the theme so
 * route casings and the heatmap keep their contrast (frontend/README.md
 * Section 9.8). */
export function basemapStyleUrl(theme: Theme): string {
  return theme === "dark"
    ? "https://tiles.openfreemap.org/styles/dark"
    : "https://tiles.openfreemap.org/styles/positron";
}
