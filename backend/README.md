# Backend — Weather-Aware Truck Routing (Django)

Stateless JSON API. It is the single source of truth for routes, weather-driven risk and the recommendation — the frontend only renders what this service returns (see top-level `README.md`, design principle 4: "the backend decides, the frontend displays"). Full product design and service table live in `../README.md`; this file is the implementation doc for this folder only.

## 1. Role in the product

- Turns an origin/destination/departure/load/interval into 3 scored truck routes.
- Places checkpoints along each route, attaches weather at each checkpoint's ETA, classifies risk, ranks the routes, and explains the winner in one line.
- Builds the 0–48 h corridor risk heatmap once per plan.
- Never trusts the frontend's math — all risk/ranking logic runs here, exactly once.

## 2. Request flows

### 2.1 Plan a trip — `POST /api/trips/plan`

```
client ──▶ apps/trips (validate) ──▶ TripPlanner.plan()
                                        │
                 1. RouteAlternativesService ──▶ RoutingProvider (Valhalla, +fallback)
                 2. core.sampling            ──▶ checkpoints + ETAs (pure, no I/O)
                 3. WeatherService           ──▶ dedupe → cache → WeatherProvider (batched)
                 4. core.risk.classify()     ──▶ one RiskResult per checkpoint
                 5. core.ranking.rank()      ──▶ sorted routes + recommendation reason
                                        │
                                   JSON response (Section 4 contract below)
```

### 2.2 Load the heatmap — `GET /api/trips/{plan_id}/heatmap`

```
client ──▶ apps/trips ──▶ HeatmapService
                             1. read corridor grid cached under plan_id
                             2. fetch/batch weather for all grid points, 49 hours, shared weather cache
                             3. core.risk.classify() per point per hour
                             4. return 49 × N risk-level grid + raw values for hover
```

### 2.3 Place autocomplete — `GET /api/geocode?q=`

```
client ──▶ apps/trips ──▶ GeocodingProvider (Photon) ──▶ 24h cache keyed by normalised query
```

### 2.4 Health / wake — `GET /api/health`

Plain 200, no logic. Used by the frontend to wake a sleeping Render instance before the real request.

## 3. Prerequisites & installation

**Requires:** Python 3.11+, pip (or `uv`/`poetry` if preferred — examples below use plain `venv`+`pip`).

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env             # fill in STADIA_API_KEY etc.
python manage.py runserver
```

**`requirements.txt`**
```
Django
djangorestframework
django-cors-headers
django-environ
httpx
polyline
shapely
gunicorn
whitenoise
```

**`requirements-dev.txt`**
```
pytest
pytest-django
respx
ruff
mypy
```

**Environment variables** (`.env`, never committed — see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `STADIA_API_KEY` | Stadia routing key (server only, never sent to the browser) |
| `ROUTING_PROVIDER` | `valhalla` |
| `ROUTING_PRIMARY_URL` | `https://api.stadiamaps.com` |
| `ROUTING_FALLBACK_URL` | `https://valhalla1.openstreetmap.de` |
| `WEATHER_PROVIDER` | `open_meteo` |
| `GEOCODER_URL` | `https://photon.komoot.io` |
| `ASSUMED_EMPTY_TRUCK_LB` | `35000` |
| `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | standard Django security settings |

**Day-to-day commands**

```bash
pytest                  # all tests
pytest core/             # fast, pure-domain tests only
ruff check . && ruff format .
mypy core/                # strict typing on the domain layer
```

## 4. Folder structure

```
backend/
  manage.py
  requirements.txt
  requirements-dev.txt
  .env.example
  config/
    settings/
      base.py             # env-driven, shared
      dev.py
      prod.py
    urls.py
    wsgi.py
  apps/
    trips/                 # API layer — thin
      views.py
      serializers.py
      urls.py
  services/                 # one class per use case
    trip_planner.py          # TripPlanner.plan(request) -> TripPlan
    route_alternatives.py    # 3-route pipeline
    weather_service.py       # dedupe, batch, cache weather lookups
    heatmap_service.py       # corridor grid + 48h risk frames
  core/                      # pure domain — no Django, no HTTP, no I/O
    models.py                 # Coordinate, Route, Checkpoint, WeatherSample, RiskLevel, RouteSummary
    geo.py                     # haversine, interpolate, offset_point, overlap_ratio, simplify
    sampling.py                 # checkpoints every N miles + ETAs
    risk/
      rules.py                    # WIND_RULES, RAIN_RULES, SNOW_RULES, LOAD_RULES as data
      classifier.py                # classify(sample, load_lb) -> RiskResult
    ranking.py                     # summarize() + rank()
    heatmap.py                      # build_grid(), score_grid()
  providers/                 # adapters — the only layer allowed to call outside APIs
    routing/
      base.py                 # RoutingProvider protocol
      valhalla.py               # serves both Stadia and public Valhalla (base_url differs)
      fallback.py                # FallbackRoutingProvider(primary, secondary)
    weather/
      base.py
      open_meteo.py
    geocoding/
      base.py
      photon.py
    registry.py                # builds providers from settings (dependency injection)
  tests/                      # mirrors every folder above
    core/
    providers/
    services/
    apps/
```

## 5. Architecture & design patterns

### 5.1 Layered architecture — one-way imports only

```
┌─────────────────────────────────────────────────────────────┐
│ API layer · apps/trips                                       │
│ validates input → calls exactly one service → serializes out │
└───────────────────────────┬────────────────────────────────┘
                             │
┌───────────────────────────▼────────────────────────────────┐
│ Services · one class per use case                            │
│ TripPlanner · RouteAlternativesService                       │
│ WeatherService · HeatmapService                               │
└──────────────┬─────────────────────────────┬─────────────────┘
               │                             │
┌──────────────▼──────────────┐ ┌───────────▼─────────────────┐
│ Core · pure Python, no I/O   │ │ Providers · adapters          │
│ sampling, ETAs                │ │ RoutingProvider → Valhalla    │
│ risk rules + classifier       │ │ WeatherProvider → Open-Meteo  │
│ ranking, heatmap scoring      │ │ GeocodingProvider → Photon    │
└───────────────────────────────┘ └────────────────────────────┘
```

A layer may only call downward. `core/` never imports Django, `httpx`, or anything from `services/` or `providers/` — that's what makes it testable in milliseconds with zero mocks.

### 5.2 Design patterns in use

| Pattern | Where | Why it's here |
| --- | --- | --- |
| **Strategy / Adapter** | `providers/routing/*.py`, `weather/*.py`, `geocoding/*.py` behind `Protocol` interfaces | Swap Stadia for Mapbox, or Open-Meteo for a paid API, by adding one class — nothing above the provider layer changes |
| **Decorator-style wrapping** | `FallbackRoutingProvider(primary, secondary)` | Wraps one provider with retry-to-secondary behavior without either provider knowing about the other |
| **Dependency injection** | `providers/registry.py` | Services receive provider instances built from settings; nothing is hardcoded or imported directly, so tests inject fakes instead |
| **Service layer** | `services/*.py` | One class per use case (`TripPlanner`, `RouteAlternativesService`, …) keeps orchestration out of views and out of the domain |
| **Table-driven logic (rules as data)** | `core/risk/rules.py` | Thresholds and load-escalation rules are data rows, not if/elif chains — changing a number never touches code |
| **Immutable value objects** | `core/models.py` (frozen dataclasses) | `Route`, `Checkpoint`, `WeatherSample` etc. can't be mutated after creation — safe to share across threads, trivial to compare in tests |
| **Stateless service, cache-only shared state** | whole backend | No ORM, no persistence layer; the Django cache is the only thing shared between requests, and it's explicitly ephemeral (Section 9 of the top-level README) |

### 5.3 Clean code rules enforced here

- Views stay thin: validate → call one service → return. No business logic in `apps/trips`.
- Every branch has a test; no magic numbers (thresholds/intervals/cache lifetimes are named constants or settings).
- `core/` takes the current time as an argument — nothing in the domain reads the clock or the network, so tests never depend on either.
- Typed exceptions (`ProviderError`, `NoRouteError`) are mapped to the API's one error shape in exactly one place.
- `ruff` + `mypy --strict` on `core/` run in CI on every push, not relied on from memory.

## 6. Testing

| Layer | How | Example cases |
| --- | --- | --- |
| Risk thresholds | `pytest.mark.parametrize` over every boundary | wind 24.9 → Low, 25 → Moderate; rain 1.00 → Severe, 1.01 → No Travel |
| Load rules | table of wind × load cases | 40 mph + 40,001 lb → Severe; 50 mph + 30,001 lb → No Travel |
| Sampling | synthetic straight-line route | checkpoint count, increasing ETAs, `segment_miles` sums to route length |
| Ranking | hand-built summaries | each tie-breaker decides one case; No Travel always ranks last |
| 3-route pipeline | fake `RoutingProvider` | duplicates rejected, slow routes rejected, widened detour fills a short trip's 3rd route, a merely-slow-but-distinct candidate is reused as a last resort, honest warning only when no 3rd path exists at all |
| Providers | `respx` mocks of recorded responses | polyline precision 6 decode, cm→inch snow conversion |
| API | DRF `APIClient` with fake providers | 400 on bad input, 422 on no route, 502 on provider failure, response matches the contract |
