from .base import *  # noqa: F403

DEBUG = False

# Both Render and Railway terminate TLS at their edge and forward requests
# to this container over plain internal HTTP — without this, Django never
# sees a "secure" request, so SECURE_SSL_REDIRECT below fires on every
# single request (including CORS preflights, which the spec forbids from
# following a redirect) even though the client really did connect over
# HTTPS. Trusting X-Forwarded-Proto is what tells request.is_secure() the
# truth.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Render terminates TLS for every free-tier service, so HSTS is safe to
# enable unconditionally here. Starts at 1 day rather than the usual
# 1-year recommendation — raise it once the domain is confirmed stable.
SECURE_HSTS_SECONDS = 86400
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
