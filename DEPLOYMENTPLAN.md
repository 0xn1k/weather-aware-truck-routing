# Deployment Plan — Corridor

Two independent deploys: the Django backend (API) and the Vite/React frontend. They
need each other's URLs, so the order below avoids the chicken-and-egg problem —
backend first, frontend second, then one final pass back on the backend to allow
the frontend's real origin through CORS.

Both run as **two separate services in the same Railway project** (one paid account,
one place to manage both) — Railway has no built-in static-site server the way
Vercel does, so the frontend service ships as a small Dockerfile (Node build →
Caddy serving `dist/`) rather than a zero-config static deploy. Configs already in
the repo:
- `backend/railway.json` — Railpack build (`uv sync` + gunicorn)
- `frontend/railway.json` + `frontend/Dockerfile` + `frontend/Caddyfile` — Docker build (`npm run build` → Caddy serves `dist/`, with SPA fallback to `index.html` for client-side routing)
- `backend/render.yaml` / `frontend/vercel.json` — kept as alternative/fallback platforms if you'd rather split hosts

Everything below assumes **both services on Railway**. Render/Vercel-specific notes
are called out where they differ.

---

## 0. Prerequisites

- [ ] A [Stadia Maps](https://stadiamaps.com) account + API key (primary routing provider — `providers/routing/valhalla.py`). Free tier is enough for a demo.
- [ ] Railway account (paid, per your existing service) and Vercel account.
- [ ] Repo pushed to GitHub (both platforms deploy from a connected repo).

---

## 1. Deploy the backend to Railway

1. In the Railway project, create (or point your existing service at) this repo.
2. **Settings → Root Directory** → set to `backend`. (Railway doesn't read `rootDir` from a config file the way Render does — this has to be set in the dashboard.)
3. Confirm `backend/railway.json` is picked up (Railway auto-detects it at the configured root). It already defines the build and start commands:
   - Build: `pip install uv && uv sync --no-dev && uv run python manage.py collectstatic --noinput`
   - Start: `uv run gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
   - Healthcheck: `/api/health`
4. **Variables tab** — set these (Railway config files don't support env vars, only the dashboard does):

   | Variable | Value |
   | --- | --- |
   | `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
   | `DJANGO_SECRET_KEY` | generate one: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `ALLOWED_HOSTS` | `.up.railway.app` (or your custom domain, once you have one) |
   | `CORS_ALLOWED_ORIGINS` | leave blank for now — comes back in Step 4 |
   | `STADIA_API_KEY` | your Stadia Maps key |
   | `ROUTING_PROVIDER` | `valhalla` |
   | `ROUTING_PRIMARY_URL` | `https://api.stadiamaps.com` |
   | `ROUTING_FALLBACK_URL` | `https://valhalla1.openstreetmap.de` |
   | `WEATHER_PROVIDER` | `open_meteo` (or `fake` — see Section 5 below) |
   | `GEOCODER_URL` | `https://photon.komoot.io` |
   | `ASSUMED_EMPTY_TRUCK_LB` | `35000` |

5. Deploy. Once it's live, note the public URL Railway assigns (Settings → Networking → Generate Domain if one isn't already there) — call it `BACKEND_URL`.
6. Sanity check: `curl https://<BACKEND_URL>/api/health` → `{"status": "ok"}`.

### If using Render instead

`backend/render.yaml` already encodes `rootDir: backend` and most env vars directly —
Render reads it automatically via "Blueprint" deploy. You'll still need to fill in
`STADIA_API_KEY` and `CORS_ALLOWED_ORIGINS` manually (marked `sync: false` in the file,
deliberately not committed). Render's free tier sleeps after 15 min idle — the
frontend's health-check-on-load banner (Section 4) exists specifically to paper over
that; Railway on a paid plan doesn't have this problem by default (see your earlier
conversation about this — Railway's sleep/"Serverless" feature is opt-in, not default).

---

## 2. Deploy the frontend to Railway (second service, same project)

1. In the same Railway project, **create a new service** from the same GitHub repo.
2. **Settings → Root Directory** → set to `frontend`.
3. Confirm `frontend/railway.json` is picked up — it points the build at `frontend/Dockerfile` (Docker builder, not Railpack). The Dockerfile does a Node build stage (`npm ci && npm run build`) then copies `dist/` into a `caddy` image; `frontend/Caddyfile` serves it with the SPA fallback (`try_files {path} /index.html`) so client-side routes survive a hard refresh.
4. **Variables tab** → add:

   | Variable | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | `https://<BACKEND_URL>` from Step 1 |

   Vite inlines this into the JS bundle **at build time**, not runtime — it only works
   because `frontend/Dockerfile` declares `ARG VITE_API_BASE_URL` before `npm run
   build`. Railway auto-matches a dashboard Variable to a Dockerfile `ARG` of the same
   name (confirmed against Railway's own docs); no other config needed. If you ever
   change the backend URL, you must **redeploy the frontend service**, not just
   restart it — a restart reuses the already-built image with the old value baked in.
5. Deploy. Generate a domain the same way as Step 1 (Settings → Networking). Note the
   frontend's public URL — call it `FRONTEND_URL`.

### If using Vercel instead

`frontend/vercel.json` already defines the build (`npm run build`, Vite framework, SPA
rewrites) — Vercel picks it up automatically, zero-config, no Dockerfile/Caddy needed
(Vercel serves static builds natively, unlike Railway). Set `VITE_API_BASE_URL` the
same way under Environment Variables; Vercel also treats it as build-time.

---

## 3. Close the loop: allow the frontend through CORS

Go back to Railway (or Render) → Variables → set:

```
CORS_ALLOWED_ORIGINS=https://<FRONTEND_URL>
```

Redeploy/restart the backend service so it picks up the new value (Railway restarts
automatically on a variable change in most cases — confirm it actually redeployed).

---

## 4. Verify end-to-end

- [ ] Open `https://<FRONTEND_URL>` — the page loads, dark/light toggle works.
- [ ] Submit a trip (e.g. "Try an example" → Chicago → Denver) → 3 routes come back, map renders, heatmap loads.
- [ ] Open browser devtools → Network tab → confirm no CORS errors on `/api/trips/plan`.
- [ ] Click the "Live weather" / "Dummy weather" header toggle (Section 5) and confirm it flips without erroring.
- [ ] Hard-refresh and confirm state resets sanely (no stale cached plan).

---

## 5. The weather-provider toggle, post-deploy

The header button flips the backend between real Open-Meteo data and the
deterministic dummy generator (`providers/weather/fake.py`) **without a redeploy** —
see `providers/registry.py`'s `set_weather_provider_name`. A few things worth knowing
once this is live on a real host:

- It's **process-global, not per-visitor**. Every browser hitting the backend sees
  whichever mode was last set — there's no per-session isolation. Fine for a
  single-person demo; don't rely on it if multiple people might be testing
  simultaneously and expect independent state.
- It **resets to whatever `WEATHER_PROVIDER` is set to in the environment** on every
  redeploy or restart. If you want it to default to dummy weather after a deploy
  (e.g. to avoid immediately burning real API quota), set the `WEATHER_PROVIDER` env
  var to `fake` rather than relying on remembering to click the toggle.
- The endpoint (`GET`/`POST /api/weather-provider`) is intentionally
  **unauthenticated** — this whole app has no auth system. Don't reuse this pattern
  on a service with real users/data.
- Open-Meteo's free tier is capped at 10,000 calls/day — real-world testing during
  development exhausted it more than once this session. If "Live weather" starts
  returning a 502 with a rate-limit message, that's expected; switch back to
  "Dummy weather" and wait for the daily reset.

---

## 6. Known operational limitations (carried over from the design, not new)

- **No database, no persistence.** Cache is in-process memory
  (`CACHES` → `LocMemCache` in `backend/config/settings/base.py`). A restart clears
  it — cached weather lookups, cached plan contexts for the heatmap endpoint (expires
  in ~60 min anyway), and the weather-provider toggle all reset together.
- **Single worker process assumed.** Both `railway.json` and `render.yaml` start
  gunicorn with no `--workers` flag (defaults to 1). The in-memory cache and the
  weather-provider toggle both depend on this — if you ever scale to multiple
  workers/replicas, neither is shared across them, and you'd need to move both to a
  real shared store (e.g. Redis) first.
- **Routing has a hard distance cap.** Valhalla rejects origin/destination pairs
  more than ~930 mi apart (straight-line). The frontend's From/To pickers already
  filter this out before submission (`MAX_TRIP_DISTANCE_MI` in
  `frontend/src/features/trip-form/TripForm.tsx`), so this shouldn't surface as a
  live-site bug, just something to know if routing ever changes.

---

## 7. Redeploying after future changes

Both platforms redeploy automatically on push to the connected branch (`main`) —
no manual steps beyond the one-time setup above. If you change which env vars are
needed (new provider, new setting), update them in both:
- The platform dashboard (Railway/Render/Vercel) — the actual source of truth at runtime.
- `backend/.env.example` and this file — so the docs don't drift from reality.
