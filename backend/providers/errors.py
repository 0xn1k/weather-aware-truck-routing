class ProviderError(Exception):
    """An outside API failed after retries (mapped to 502 by the API layer)."""


class NoRouteError(Exception):
    """The routing engine found no path between the two points (mapped to 422)."""
