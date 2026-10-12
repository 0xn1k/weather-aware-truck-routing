import type { TripPlan } from "@/api/types";
import { FewerRoutesBanner, NoTravelBanner } from "@/lib/Banner";
import { sortByRank } from "@/lib/routeOrder";
import { RecommendationBanner } from "./RecommendationBanner";
import { RouteCard } from "./RouteCard";

const LETTERS = ["A", "B", "C", "D", "E"];

interface RouteListProps {
  plan: TripPlan;
  selectedRouteId: string;
  onSelectRoute: (id: string) => void;
  onOpenDetails: (id: string) => void;
}

export function RouteList({ plan, selectedRouteId, onSelectRoute, onOpenDetails }: RouteListProps) {
  const routes = sortByRank(plan.routes);
  const fastestId = plan.routes.reduce((fastest, r) =>
    r.duration_s < fastest.duration_s ? r : fastest,
  ).id;
  const noTravelWarning = plan.warnings.find((w) => w.includes("Do not travel"));
  const fewerRoutesMatch = plan.warnings.find((w) => w.includes("different route"));

  return (
    <div className="flex flex-col gap-3.5">
      <div>
        <h2 className="m-0 text-[16px] font-bold" style={{ color: "var(--ink)" }}>
          {plan.routes.length} route{plan.routes.length === 1 ? "" : "s"} found
        </h2>
      </div>

      {noTravelWarning && <NoTravelBanner />}
      {fewerRoutesMatch && <FewerRoutesBanner count={plan.routes.length} />}
      <RecommendationBanner reason={plan.recommendation_reason} />

      {routes.map((route, index) => (
        <RouteCard
          key={route.id}
          route={route}
          letter={LETTERS[index] ?? String(index + 1)}
          totalRoutes={plan.routes.length}
          isSelected={route.id === selectedRouteId}
          isRecommended={route.id === plan.recommended_route_id}
          isFastest={route.id === fastestId}
          onSelect={() => onSelectRoute(route.id)}
          onOpenDetails={() => onOpenDetails(route.id)}
        />
      ))}
    </div>
  );
}
