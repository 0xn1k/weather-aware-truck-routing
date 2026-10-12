from .base import *  # noqa: F403

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Render terminates TLS for every free-tier service, so HSTS is safe to
# enable unconditionally here. Starts at 1 day rather than the usual
# 1-year recommendation — raise it once the domain is confirmed stable.
SECURE_HSTS_SECONDS = 86400
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
