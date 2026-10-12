from .base import *  # noqa: F403

DEBUG = True

# Vite auto-increments to the next free port (5174, 5175, ...) whenever
# 5173 is already taken — a routine, frequent occurrence in local dev, not
# an edge case. Hardcoding just one exact origin in CORS_ALLOWED_ORIGINS
# meant every port bump silently broke every request with a CORS error.
# Dev-only: production keeps the strict, single real Vercel origin from
# CORS_ALLOWED_ORIGINS (config/settings/base.py).
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://localhost:\d+$"]
