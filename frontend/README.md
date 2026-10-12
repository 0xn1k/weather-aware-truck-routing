# Frontend — Weather-Aware Truck Routing (React)

Renders what the backend decides. No risk or ranking math lives here — this app's job is the trip form, the map, and making 49 precomputed heatmap frames feel instant on a slider. Full product design lives in `../README.md`; this file is the implementation doc for this folder only.

## 1. Role in the product

- Collects origin, destination, departure time, load weight, sampling interval.
- Shows 3 route cards with the recommendation and its one-line reason.
- Renders routes, checkpoints and the risk heatmap on a MapLibre map.
- Drives the 0–48 h slider entirely client-side — no network call per frame.

## 2. User & data flows

### 2.1 Plan a trip (primary flow)

```
TripForm (user fills in + submits)
   │  validated client-side (mirrors backend validation)
   ▼
useTripPlan() ──▶ POST /api/trips/plan ──▶ TanStack Query cache
   │
   ▼
RouteList renders 3 RouteCards + RecommendationBanner
   │  user clicks a card
   ▼
uiStore.selectedRouteId updates (Zustand) ──▶ TripMap highlights that route,
                                               fits bounds, opens its checkpoints
```

### 2.2 Explore the heatmap (slider flow)

```
plan response returns first ──▶ routes + checkpoints render immediately
                                      │
useHeatmap(plan_id) ──▶ GET /api/trips/{plan_id}/heatmap ──▶ 49 frames cached in Query
                                      │
ForecastSlider drag ──▶ uiStore.sliderHour (Zustand, no network)
                                      │
HeatmapLayer + TruckPositionLayer re-read the cached frame for that hour only
```

### 2.3 Place autocomplete

```
PlaceAutocomplete input (debounced) ──▶ usePlaceSearch() ──▶ GET /api/geocode?q=
```

## 3. Prerequisites & installation

**Requires:** Node 20+, npm.

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install react-map-gl maplibre-gl @tanstack/react-query zustand framer-motion
npm install -D tailwindcss postcss autoprefixer eslint prettier vitest @testing-library/react
npx tailwindcss init -p
cp .env.example .env.local        # set VITE_API_BASE_URL
npm run dev
```

**Dependencies and why each is here**

| Package | Purpose |
| --- | --- |
| `react`, `react-dom` | UI |
| `maplibre-gl`, `react-map-gl` | WebGL map: routes, checkpoints, heatmap |
| `@tanstack/react-query` | server state: caching, loading/error states for plan/heatmap/geocode |
| `zustand` | UI-only state: selected route, slider hour, panel open — never duplicates server state |
| `framer-motion` | the handful of motion moments listed in Section 6 |
| `tailwindcss` | styling |
| `typescript` (strict), `vite`, `eslint`, `prettier`, `vitest` | tooling, dev only |

No icon package — the approved design (Section 9) draws every icon as a hand-written inline SVG in a consistent 2–2.6px round-stroke style, not a packaged set like Lucide/Heroicons. **Geist** and **Geist Mono** (Section 9.3) load from Google Fonts — add this to `index.html`'s `<head>`:

```html
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

**Environment variables** (`.env.local`, never committed — see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | the Django backend's base URL. No API keys ever live in the browser. |

**Day-to-day commands**

```bash
npm run dev       # local dev server
npm run build     # production build
npm run lint       # eslint
npm run test        # vitest
```

## 4. Folder structure

```
frontend/
  index.html
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  .env.example
  src/
    api/
      client.ts            # fetch wrapper: base URL, JSON, typed errors
      types.ts              # TripPlanRequest, TripPlan, RouteResult, Checkpoint, Heatmap — mirrors the API contract 1:1
      hooks.ts               # useTripPlan(), useHeatmap(), usePlaceSearch() via TanStack Query
    features/
      trip-form/
        TripForm.tsx
        PlaceAutocomplete.tsx
        IntervalSelector.tsx
        validation.ts
      routes/
        RouteList.tsx
        RouteCard.tsx
        RouteDetailsModal.tsx  # trip summary, risk strip, ranking table, checkpoint table
        RecommendationBanner.tsx
        RiskBar.tsx
      map/
        TripMap.tsx
        layers/
          RouteLayer.tsx
          CheckpointLayer.tsx
          HeatmapLayer.tsx
          TruckPositionLayer.tsx
        CheckpointPopup.tsx
        Legend.tsx
      forecast/
        ForecastSlider.tsx
    state/
      uiStore.ts             # selected route, slider hour, panel open (Zustand)
    lib/
      risk.ts                  # one place for risk colours, labels and icons (values in Section 9.2)
      theme.ts                  # light/dark token objects (values in Section 9.2)
      format.ts                  # miles, durations, UTC → local time
      motion.ts                   # shared framer-motion variants (Section 6)
      Banner.tsx                  # the 4 banner variants (Section 9.6.1)
      icons/                        # one hand-drawn SVG icon per file (Section 6) — no icon package
    App.tsx                    # layout: side panel + map
    main.tsx
```

## 5. Architecture & design patterns

### 5.1 State architecture

```
┌───────────────────────────────┐   ┌────────────────────────────────┐
│ Server state (source of truth) │   │ UI-only state                    │
│ TanStack Query                  │   │ Zustand — uiStore                │
│ trip plan · heatmap · places     │   │ selectedRouteId · sliderHour      │
│ caching, retries, loading/error   │   │ panelOpen                         │
└───────────────┬────────────────┘   └────────────────┬─────────────────┘
                │                                       │
                └───────────────────┬───────────────────┘
                                    ▼
                    ┌────────────────────────────┐
                    │ features/ components         │
                    │ read both, never store either │
                    │ copy of either locally         │
                    └────────────────────────────┘
```

Nothing is duplicated between the two stores — a component that needs the plan reads it from the query cache; a component that needs "which route is selected" reads it from `uiStore`. This is the frontend's one real architectural rule.

### 5.2 Design patterns in use

| Pattern | Where | Why it's here |
| --- | --- | --- |
| **Feature-folder architecture** | `features/trip-form`, `features/routes`, `features/map`, `features/forecast` | Changing the form never touches the map; each feature owns its own components end to end |
| **Single source of truth for types** | `api/types.ts` | Mirrors the backend's Section 8 contract exactly — if the API changes shape, this is the one file that has to change |
| **Server state / UI state separation** | TanStack Query vs Zustand (5.1) | Avoids the two most common React bugs: stale duplicated server data, and UI state that resets itself after every refetch |
| **Composition over configuration** | `map/layers/*.tsx` as declarative `<Source>`/`<Layer>` components, memoized | React re-renders never rebuild the WebGL map; each layer owns its own data binding |
| **Thin presentational components, logic in hooks** | `api/hooks.ts` holds all fetching; components only read the hook's return value | Keeps `RouteCard`, `TripMap`, etc. trivial to test and trivial to restyle |

### 5.3 High-level architecture (frontend detail)

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser                                                            │
│                                                                     │
│  ┌───────────────┐   reads/writes   ┌─────────────────────────┐   │
│  │ features/*      │◀───────────────▶│ state/uiStore (Zustand)   │   │
│  │ TripForm          │                │ selectedRouteId            │   │
│  │ RouteList          │                │ sliderHour                  │   │
│  │ TripMap + layers     │                │ panelOpen                     │   │
│  │ ForecastSlider          │                └─────────────────────────┘   │
│  └────────┬──────────┘                                                │
│           │ calls                                                        │
│  ┌────────▼──────────┐    caches    ┌─────────────────────────┐        │
│  │ api/hooks.ts          │◀───────────▶│ TanStack Query cache       │        │
│  │ useTripPlan()            │                │ plan · heatmap · places      │        │
│  │ useHeatmap()                │                └─────────────────────────┘        │
│  │ usePlaceSearch()               │                                                   │
│  └────────┬──────────────────┘                                                   │
│           │ fetch                                                                   │
│  ┌────────▼──────────┐                                                               │
│  │ api/client.ts          │──── JSON over HTTPS ────▶  Django backend (/api/*)         │
│  └───────────────────┘                                                                │
│                                                                                         │
│  MapLibre draws tiles directly from OpenFreeMap — no backend hop for basemap            │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Icons & animation

**Icons — hand-drawn inline SVG, not a packaged icon library.** The approved design (Section 9) uses a small, consistent icon language: 2–2.6px stroke, round caps/joins, `currentColor` or an explicit theme token for fill, 24×24 viewBox. Keep every icon as a `.tsx` component under `lib/icons/` (one file per icon) rather than pulling in Lucide/Heroicons — the shapes in the mockup (logo mark, sun/moon toggle, swap arrows, play triangle, warning glyphs) are custom and a generic icon set won't match them. Used for:
- App logo mark (34×34 rounded-square badge, truck + weather-bolt)
- Theme toggle (sun / moon, in the segmented control)
- Form (swap From/To, Edit-trip pencil on the mobile summary bar)
- Forecast slider (play/pause, 44px circular button)
- Banners (status icon per severity — see Section 9.6)
- Legend swatches (overlapping translucent circles, not flat squares)

**Animation — `framer-motion`, kept to the exact moments the spec names** (Section 9's "Motion" row), nothing decorative beyond it:
- `RecommendationBanner` — enters with a short fade/slide when the plan result arrives
- `RouteCard` — selected state transitions (border/elevation) on click, not on hover
- `ForecastSlider` → `HeatmapLayer` — cross-fades between adjacent hour frames instead of hard-cutting, since frames are precomputed and switching is cheap
- `CheckpointPopup` / route details modal — opens with a small scale/fade instead of appearing instantly

Respect `prefers-reduced-motion`: with it on, the slider's Play advances one hour per second with no easing and the map does not animate its camera — this is a stated requirement (Section 9.7), not an optional nicety. Shared variants live in one file (`lib/motion.ts`) so every animated component uses the same easing/duration instead of each one inventing its own.

## 7. Clean code rules enforced here

- `tsconfig.json` has `strict: true`; no `any` without a named reason comment.
- `camelCase` for variables/functions, `PascalCase` for components, one component per file.
- Every `useQuery`/`useMutation` consumer handles loading and error states — no silent blank screens.
- `lib/risk.ts` is the only file allowed to map a `RiskLevel` to a colour, label or icon — nothing hardcodes a hex value elsewhere.
- Map layers never hold local component state for data that belongs in Query or `uiStore`.

## 8. Testing

| What | How |
| --- | --- |
| Risk colour/label/icon mapping | `vitest` unit tests on `lib/risk.ts` |
| Time formatting (UTC → local) | `vitest` unit tests on `lib/format.ts` |
| Form validation | `vitest` on `validation.ts` boundary cases (load 0, 80,001 lb; invalid interval) |
| Components | `@testing-library/react`, render + interaction tests for `RouteCard`, `ForecastSlider` |

## 9. UI design reference

This section documents what's in `Weather-Aware Truck Routing UI.html` — the approved visual target. The file is a self-contained mockup bundle with four states: **Desktop · light**, **Mobile · dark**, **Desktop · dark with Route B's details window open**, and a **States and components · full spec** page (the design-system reference — tokens, every component, every state, accessibility and responsive rules in one place). Open the file in a browser to see all four; the notes below are what was extracted from it.

### 9.1 Product identity

- **App name: "Corridor."** Tagline: *"Safest truck route by weather, load and time."*
- **Logo mark**: 34×34, 9px-radius rounded square in the button colour, with a truck glyph and a small weather-bolt accent — a custom SVG, not a stock icon.
- Footer attribution, always visible: *OpenStreetMap, OpenMapTiles, OpenFreeMap, Stadia Maps, Open-Meteo (CC BY 4.0)* — matches the top-level README's hosting note.

### 9.2 Design tokens — colour

Two themes, same token names, different values. `lib/risk.ts` and a small `lib/theme.ts` should be the only files that reference these — nothing else hardcodes a hex value.

| Token | Used for | Light | Dark |
| --- | --- | --- | --- |
| `bg` | Page background | `#F6F7F9` | `#0B0F14` |
| `surface` | Side panel, cards, map overlays | `#FFFFFF` | `#12171E` |
| `surface2` | Detail boxes, table headers | `#F3F4F6` | `#1A2029` |
| `ink` | Main text | `#0F172A` | `#E8ECF1` |
| `muted` | Labels, secondary text | `#5B6474` | `#9AA4B2` |
| `line` / `line2` | Borders, dividers | `#E4E7EC` / `#EEF0F3` | `#262D38` / `#1F2630` |
| `accent` | Selected route, slider, focus | `#2563EB` | `#60A5FA` |
| `accentTint` | Selected button background | `#EAF1FE` | `#16243A` |
| `btn` / `onBtn` | Primary buttons | `#0F172A` / `#FFFFFF` | `#E8ECF1` / `#0B0F14` |
| `recBg` / `recInk` | "Recommended" tag | `#E6F4EC` / `#166534` | `#10291B` / `#7DD3A0` |
| `routeOther` | Unselected route lines | `#9CA3AF` | `#56606C` |
| `bad` | Errors, severe counts | `#B42318` | `#FF8A80` |
| `inputBg` / `inputBorder` | Form fields | `#FFFFFF` / `#D5D9E0` | `#0B0F14` / `#323B47` |
| `chip` | Neutral pill background | `#F1F3F5` | `#222A35` |

Contrast is a hard requirement, not a suggestion: 4.5:1 minimum body text on its background in both themes (`muted` on `surface` measures 6:1 light / 7.5:1 dark).

**Risk level colours** (fill / tint-background pair, brightened in dark mode to hold contrast against the map):

| Level | Light fill | Light tint | Dark fill | Dark tint |
| --- | --- | --- | --- | --- |
| Low | `#22A05A` | `#E4F4EA` | `#43C07A` | `#16301F` |
| Moderate | `#E8B21F` | `#FBF0CF` | `#F2C230` | `#3A3114` |
| High | `#F07C1F` | `#FDE6D2` | `#F59A45` | `#3D2714` |
| Severe | `#D93A2E` | `#FADCD9` | `#F0574B` | `#3F1C1A` |
| No travel | `#6D35A8` | `#EFE5F8` | `#B27FE0` | `#2C1D3D` |

This table belongs in `lib/risk.ts` exactly as shown — it's the single source of truth the top-level README already asked for, now with real values instead of placeholders.

### 9.3 Typography

- **Geist** for UI text, **Geist Mono** for anything numeric or time-based: load weight input, mile markers, the forecast slider's `+9 h · Tue 15:00` label, checkpoint tables. Both load from Google Fonts (install snippet in Section 3).
- Weights used: 400 (body), 500, 600 (labels, buttons), 700 (headings, card titles).
- Scale observed: 12–13px (meta/labels) · 14–15px (body, inputs) · 15.5–17px (card/section titles) · 21px (spec section headings).

### 9.4 Spacing & control sizing

- Every interactive control (inputs, buttons, the swap/edit/theme-toggle buttons) is **44px tall** — this is also the accessibility touch-target minimum (Section 9.7), so don't shrink it on desktop.
- Inputs: 1px `inputBorder` normally, **2px `accent`** border on focus, **2px `bad`** border + `aria-invalid="true"` + an `aria-describedby`-linked error line on validation failure.
- Border radius: 10px (inputs, segmented controls), 12px (banners, buttons), 16–18px (cards, modal panels), 999px (pills/badges).
- Primary CTA button is 48px tall (slightly taller than other controls), filled with `btn`/`onBtn`.

### 9.5 Layout & breakpoint

Single breakpoint at **960px**, matching `features/` boundaries already in the folder structure:

| Width | Layout |
| --- | --- |
| ≥ 960px | Side panel (`aside`, trip form + route cards, scrolls independently) fixed-width-ish on the left; map (`main`, `position: sticky; height: 100vh`) fills the rest and never scrolls with the page. |
| < 960px | Map on top with the slider overlaid on it; route cards live in a bottom sheet (rounded top corners, drag handle, `border-radius: 22px 22px 0 0`) rising from the bottom; the form collapses into a compact summary bar (origin → destination, departure, load, interval as one line) with a dedicated **Edit** button that reopens the form. |

Route cards show 4 stats (Distance, Drive time, Departs, Arrives) at ≥960px and drop to 3 (Distance, Drive time, Arrives) in the mobile bottom sheet — don't just shrink the same grid, remove a column.

### 9.6 Component inventory

Maps directly onto the folders in Section 4.

| Component | Folder | Notes from the mockup |
| --- | --- | --- |
| `Header` | `App.tsx` | Logo + name + tagline, theme toggle (2-button segmented pill, sun/moon) |
| `TripForm` | `trip-form/` | From/To with a swap button between them (44px, up/down arrow icon); Departure shows the resolved local timezone inline (`Your local time (CDT)`) |
| `PlaceAutocomplete` | `trip-form/` | `role="listbox"`/`role="option"`, selected option gets `accentTint` background |
| `IntervalSelector` | `trip-form/` | 3-way segmented control (10/25/50 mi), matches the theme toggle's visual pattern |
| `RouteCard` | `routes/` | Route-letter badge (30px circle), "Recommended" (green tint) and/or "Fastest" (neutral chip) tags, "Rank X of 3" right-aligned; selected card = 2px accent border + shadow, others = 1px neutral border, no shadow |
| `RiskBar` | `routes/` | 5-segment bar proportional to miles per level, Low→No-travel order |
| Route details modal | `routes/` (new: `RouteDetailsModal`) | Header + close · 6-tile trip summary · corridor risk strip (origin→destination, left to right) · ranking table (5 rules × 3 routes, this route's column highlighted, ties labelled "tie") · weather extremes · full scrollable checkpoint table (High+ rows tinted) · a 5-step "how these numbers were worked out" explainer |
| `TripMap` + layers | `map/` | See 9.8 — the mockup draws a stylised SVG map; colours/line-weights/blur still apply to the real MapLibre layers |
| `Legend` | `map/` | List of risk levels, each with an overlapping-circle swatch icon (not a flat square) |
| `ForecastSlider` | `forecast/` | Circular play/pause button (44px) · label row (`Forecast +9h · Tue 15:00` in Geist Mono + current truck position caption) · full-width range input, 0–48 step 1 |
| `Banner` | new: `lib/Banner.tsx`, shared by `routes/` and `App.tsx` | 4 variants — see 9.6.1 |
| Empty / loading state | `App.tsx` or `trip-form/` | See 9.6.2 |

**9.6.1 Banner variants** — `role="status"` (informational) or `role="alert"` (error), icon + text, 12px radius:

| Variant | Background | Trigger | Copy example |
| --- | --- | --- | --- |
| No-travel | No-travel tint (purple) | every route crosses No-travel conditions | "Do not travel at this departure time" + "Routes are still ranked below." |
| Fewer than 3 routes | Low tint (green) | the 3rd candidate failed the overlap/time filter (Section 5.1 of the backend design) | "Only 2 different routes exist for this trip" |
| Waking up | Neutral `chip` + spinner icon | Render cold start | "Waking up the server…" — "first request takes about a minute, your trip is kept" |
| Weather unavailable | High tint (orange), `role="alert"` | provider failed after retries | "Weather data is unavailable right now" + a 44px "Try again" button |

**9.6.2 Empty & loading**
- **Empty** (before first search): dashed-border placeholder card, map shows the basemap only — no legend, no slider.
- **Loading**: a 3-step status list that mirrors the backend's actual request order (Section 2.1 of this README) — *Done · 3 truck routes found* → *Now · weather at N checkpoints* → *Next · ranking and heatmap*. On a re-plan, the previous result stays visible but dimmed — the screen must never go blank.

### 9.7 Accessibility — these are requirements, not polish

- Touch targets ≥ 44×44px everywhere, including desktop.
- Tab order: form → route cards → map controls → slider. Slider's arrow keys move one hour.
- Risk is never colour-only: every risk indicator pairs a colour with a text label or icon.
- Error fields: `aria-invalid="true"` + `aria-describedby` pointing at the visible error text.
- `prefers-reduced-motion`: Play advances the slider one hour per second with no easing; the map does not animate its camera.

### 9.8 Map: mockup vs. real implementation

The mockup renders the map as **hand-drawn SVG** (stylised state borders, rivers, text labels) — it's a stand-in so the file has no external tile dependency, not a suggestion to drop MapLibre/OpenFreeMap. Carry over its *visual language* to the real `map/layers/*.tsx`, not its implementation:
- Route casing: a dark outline (`bg`/`land` colour, thicker) under a coloured line — selected route wider (e.g. 20px casing / 11px line) than unselected routes (14px / 7px), selected uses `accent`, others use `routeOther`.
- Checkpoint dots: filled with the risk colour, thin dark stroke (~1.8px) for separation against both themes.
- Heatmap: soft Gaussian-blurred radial gradients in the risk tint colours, layered by severity (wide low-opacity Low-level wash, smaller higher-opacity hotspots for Moderate/High/Severe at the actual risk centres) — this is the visual target for `HeatmapLayer`, not literal geometry to copy.
