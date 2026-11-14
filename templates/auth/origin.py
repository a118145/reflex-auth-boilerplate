"""Did an HTTP request come from this app's own pages?

Used by every state-changing backend route (``endpoints``, ``upload_gate``).
Together with ``SameSite=Lax`` on the session cookie this is the CSRF defence.
"""

from urllib.parse import urlsplit

from reflex.config import get_config
from starlette.requests import Request

from . import settings


def origin_of(url: str | None) -> str:
    """``scheme://host[:port]`` of a URL, or ``""`` if it has none."""
    parts = urlsplit(url or "")
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def from_this_app(request: Request) -> bool:
    config = get_config()
    allowed = {origin_of(config.api_url), origin_of(config.deploy_url)} - {""}
    origin = request.headers.get("origin")
    if origin is not None and origin != "null":
        return origin in allowed
    # No usable Origin (some privacy settings send "null"): fall back to the
    # browser's own verdict. A sandboxed attacker iframe reports cross-site.
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is None and origin == "null" and settings.ALLOW_NULL_ORIGIN:
        return True
    return fetch_site in ("same-origin", "same-site")
