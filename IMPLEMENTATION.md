# Implementation Plan

This turns the design in `README.md` into an ordered, checkable build sequence. One repo, two folders: `backend/` (Django) and `frontend/` (React). Each phase lists what to create, in which folder, and how to know it's done before moving to the next phase. Build bottom-up — core before providers before services before API before UI — so every layer can be tested with fakes before the layer above it exists.

```
weather-truck-routing/
  backend/
  frontend/
  docs/
  .github/workflows/ci.yml
  README.md
  IMPLEMENTATION.md
```

---

## Phase 0 — Repo and tooling ✅

- [x] `backend/`, `frontend/`, `docs/` *(no `docs/` folder yet — not needed so far)*, `.github/workflows/` folders
- [x] `backend/.env.example`, `frontend/.env.example` (no real secrets committed)
- [x] Root `.gitignore` (venv, node_modules, `.env`, `__pycache__`, build output)
- [x] `.github/workflows/ci.yml` — both jobs real, not no-op (see Phase 8)

**Done when:** repo has both folders, CI workflow file exists and runs (even if its jobs are empty).

---

## Phase 1 — Backend scaffold ✅ (built with uv, not venv/pip — see `backend/IMPLEMENTATION_PLAN.md`)

- [x] `uv init --app`, installed Django, djangorestframework, django-cors-headers, django-environ, httpx, polyline, shapely, gunicorn, whitenoise; dev: pytest, pytest-django, respx, ruff, mypy
- [x] `django-admin startproject config .` inside `backend/`
- [x] `config/settings/base.py`, `dev.py`, `prod.py` (env-driven via django-environ)
- [x] `apps/trips` app registered
- [x] `GET /api/health` returning `{"status": "ok"}` — verified live

**Done when:** `python manage.py runserver` works locally and `/api/health` returns 200.

---

## Phase 2 — Core domain (`backend/core/`, pure Python, no Django/HTTP imports) ✅

- [x] `models.py` — `Coordinate`, `Route`, `Checkpoint`, `CheckpointPlan`, `Maneuver`, `Vehicle`, `WeatherSample`, `RiskLevel` (IntEnum), `RouteSummary`, `PeakReading`, `Place` (all frozen dataclasses)
- [x] `geo.py` — `haversine`, `interpolate`, `offset_point`, `bearing`, `overlap_ratio`, `simplify`
- [x] `risk/rules.py` — `WIND_RULES`, `RAIN_RULES`, `SNOW_RULES` as `Threshold` data; `LOAD_RULES` table
- [x] `risk/classifier.py` — `classify(sample, load_lb) -> RiskResult`
- [x] `sampling.py` — checkpoint placement at mile 0 / every N miles / destination, with ETA per checkpoint
- [x] `ranking.py` — `summarize()` and `rank()`, tie-break criteria in public `RANKING_CRITERIA`
- [x] `heatmap.py` — `build_grid()`, `score_grid()`

**Status:** 79 tests in this layer alone, all green. No file in `core/` imports Django or `httpx`.

---

## Phase 3 — Providers (`backend/providers/`) ✅

- [x] `routing/base.py` — `RoutingProvider` protocol
- [x] `routing/valhalla.py` — one class, `base_url` differs for Stadia vs public Valhalla
- [x] `routing/fallback.py` — `FallbackRoutingProvider(primary, secondary)`
- [x] `weather/base.py`, `weather/open_meteo.py`
- [x] `geocoding/base.py`, `geocoding/photon.py`
- [x] `registry.py` — builds providers from settings

**Status:** `respx`-mocked tests pass for every provider — polyline precision 6 decode verified, snow cm→inch conversion verified from `hourly_units`, fallback switches on `ProviderError` only (not on a genuine `NoRouteError`).

---

## Phase 4 — Services (`backend/services/`) ✅

- [x] `route_alternatives.py` — the 5-step pipeline (alternates → preference variants → detour → filter by overlap/time → label)
- [x] `weather_cache.py` — shared cache-key scheme (extracted so `weather_service.py` and `heatmap_service.py` don't duplicate it)
- [x] `weather_service.py` — dedupe checkpoints by rounded lat/lon, read cache, batch-fetch the rest
- [x] `trip_planner.py` — `TripPlanner.plan(request) -> TripPlan`, orchestrates the above + core, assigns per-route `rank`
- [x] `heatmap_service.py` — corridor grid + 49-hour scoring, shares the weather cache with checkpoints
- [x] Cache wiring: local memory for dev, settings flag ready to point at Redis

**Status:** pipeline tests pass against a fake `RoutingProvider` (duplicates rejected by overlap, step-1 candidates skip the time filter by design, 2-route fallback produces a warning not a fake third route); weather dedupe/caching tested independently of any real provider.

---

## Phase 5 — API layer (`backend/apps/trips/`) ✅

- [x] `serializers.py` — matches README Section 8's contract, plus `rank` and `worst_checkpoint`/`peak_wind`/`peak_rain`/`peak_snow` (added once the frontend's route cards and details modal needed them — `core.ranking.summarize()` already computed these, they just weren't exposed yet)
- [x] `views.py` — thin: validate → call one service → serialize
- [x] `urls.py` — `POST /api/trips/plan`, `GET /api/trips/{plan_id}/heatmap`, `GET /api/geocode`, `GET /api/health`
- [x] Error mapping: `ProviderError` → 502, `NoRouteError` → 422, serializer errors → 400, unknown/expired `plan_id` → 404 (not in the original error table, a real case it missed)

**Status:** DRF `APIClient` tests cover every status code above and the full contract shape. Backend is functionally complete: 165 tests, ruff clean, mypy clean across `core/`, `providers/`, `services/`, `apps/`.

---

## Phase 6 — Frontend scaffold (`frontend/`) ✅ (scaffolded by hand, not `npm create vite` — a non-empty dir blocked its interactive prompt)

- [x] Vite + React + TS strict, Tailwind, ESLint flat config, Vitest
- [x] Install: react-map-gl, maplibre-gl, @tanstack/react-query, zustand, framer-motion — **note:** pinned to `maplibre-gl@^6.14.0` / `react-map-gl@^8.1.3`, not the `^4.7.1` / `^7.1.7` originally planned here, because `npm audit` flagged a critical XSS sanitizer bypass in `maplibre-gl` with no fix available in the 4.x line
- [x] `api/types.ts` — mirrors the Section 8 contract 1:1, including `rank` and the peaks/worst-checkpoint fields added during Phase 5
- [x] `api/client.ts` — typed fetch wrapper, base URL from `VITE_API_BASE_URL`, typed `ApiError`
- [x] `api/hooks.ts` — `useTripPlan()`, `useHeatmap()`, `usePlaceSearch()`, `useHealthCheck()` (retries to ride out Render's cold start)

**Status:** `npm run build`, `tsc -b`, and `eslint .` all pass clean; `npm audit --omit=dev` reports 0 vulnerabilities.

---

## Phase 7 — Frontend features (`frontend/src/features/`) ✅ (built from the design mockup; see gaps below)

- [x] `trip-form/` — `TripForm`, `PlaceAutocomplete`, `IntervalSelector`, `validation.ts`, plus `RankingExplainer` and `TryExamples` (sidebar onboarding aids from the v2 mockup)
- [x] `routes/` — `RouteList`, `RouteCard`, `RecommendationBanner`, `RiskBar`, `RouteDetailsModal`, `TripSummaryKpis`
- [x] `map/` — `TripMap` + layers: `RouteLayer`, `CheckpointLayer`, `HeatmapLayer`, `TruckPositionLayer`, `CheckpointPopup`, `Legend`
- [x] `forecast/ForecastSlider` — 0–48h range input, play/pause, reduced-motion-aware step rate
- [x] `state/uiStore.ts` (Zustand: theme, selected route, slider hour, details modal, form expanded)
- [x] `lib/risk.ts`, `lib/format.ts`, `lib/theme.ts`, `lib/motion.ts`, `lib/Banner.tsx`, `lib/icons/*` (hand-drawn SVGs, no icon package), `lib/SectionHeader.tsx`

**Status:** `tsc -b`, `eslint .`, `npm run build`, and 17 vitest unit tests (risk/format/validation) all pass. **Known gaps against the mockup** — not yet built: the mobile bottom-sheet drag-handle pattern (current layout degrades to a simple stacked mobile view instead); not yet verified in a live browser (dev server boot + HTML response checked via curl only, no visual pass).

---

## Phase 8 — Integration, CI, polish ✅ mechanism ready; ⏳ not yet run on a real push

- [x] CORS mechanism ready: `CORS_ALLOWED_ORIGINS` is env-driven (`config/settings/base.py`), defaults to `localhost:5173`; the real Vercel origin gets set as a Render env var at deploy time (see `render.yaml`, `sync: false`)
- [x] `.github/workflows/ci.yml`: backend job (`uv`: ruff, mypy, pytest) + frontend job (`npm`: eslint, tsc, vitest, build) — not yet exercised by an actual GitHub push/PR
- [x] Form validation mirrored client- and server-side: load 1–80,000 lb, interval ∈ {10,25,50}, departure not in the past / within 16 days — same rules, independently implemented in `TripPlanRequestSerializer` and `features/trip-form/validation.ts`

**Status:** every command the CI workflow runs has been run locally and passes. The workflow file itself hasn't fired yet since nothing's been pushed to GitHub.

---

## Phase 9 — Deploy ⏳ config ready; needs your accounts/credentials to actually run

- [x] `backend/render.yaml` — Blueprint with every env var from README Section 13 pre-listed (`STADIA_API_KEY` and `CORS_ALLOWED_ORIGINS` marked `sync: false` since only you can supply those)
- [x] `frontend/vercel.json` — build command, output dir, SPA rewrite
- [x] `config/settings/prod.py` — `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` (1 day, `includeSubDomains`) added and verified via `manage.py check --deploy`; `collectstatic` verified to run clean
- [x] Frontend calls `/api/health` on load (`useHealthCheck`, retries for ~30s) to wake a sleeping Render instance, shows the "waking up" banner meanwhile
- [ ] **Blocked on you:** create a Stadia Maps account (free, no card) for `STADIA_API_KEY`; create a Render account and connect this repo; create a Vercel account and connect this repo; set `CORS_ALLOWED_ORIGINS` on Render to the real Vercel URL once it exists. None of this is something I can do from here — it needs your credentials.

**Done when:** the live Vercel URL completes a real plan request end-to-end against the live Render backend.

---

## Phase 10 — Docs and walkthrough ⏳ mostly blocked on Phase 9 / on you

- [x] Local setup and running tests are documented in `backend/README.md` and `frontend/README.md` already (both written before any code existed, now verified accurate against the real implementation)
- [ ] "Known limitations" section — worth filling in once you've tried the app live (mobile bottom-sheet gap, maplibre-gl bundle size, free-tier weather call budget from Section 9)
- [ ] **Blocked on you:** the Loom walkthrough is a screen recording with your voice — I can't record it. The script is ready in Section 13 of the root `README.md` whenever you're ready to record.

---

## Notes carried over from design discussion

- Keep `risk/rules.py` and `classifier.py` exactly as sketched in README Section 5.4 (three named factors, no registry/lambda abstraction) until a 4th weather condition is actually added — see README Section 9's "New hazard" row for the upgrade path when that happens.
- Cache starts as local memory; do not treat "add more Django instances" as free scaling until `CACHES` is pointed at Redis (see README Section 9).
