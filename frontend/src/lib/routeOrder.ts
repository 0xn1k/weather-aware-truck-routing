import type { RouteResult } from "@/api/types";

/** Display order for the route list and its A/B/C letters: recommended
 * route first (rank 1), then the rest best-to-worst — `rank` is already
 * computed from no-travel miles, then severe/high miles, then avg risk,
 * then drive time (core/ranking.py), so sorting by it puts the
 * recommended route on top followed by increasing risk, instead of
 * whatever order the routing pipeline happened to produce them in. Used
 * by both RouteList (render order) and App.tsx (letter lookups for the
 * summary/details views) so the same route always gets the same letter
 * everywhere on the page. */
export function sortByRank(routes: RouteResult[]): RouteResult[] {
  return [...routes].sort((a, b) => a.rank - b.rank);
}
