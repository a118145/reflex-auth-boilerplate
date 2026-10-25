"""Backend HTTP routes under ``/_auth`` — the only code that touches the cookie.

A Reflex event cannot set an HttpOnly cookie (it talks over the WebSocket),
so signing in and out are plain HTTP requests to the backend, mounted with
``rx.App(api_transformer=auth_api())``:

| Route | Does |
| --- | --- |
| ``GET  /_auth/link?t=…`` | Shows a "Sign in" button. Spends nothing. |
| ``POST /_auth/link`` | Spends the link token, sets the cookie, redirects. |
| ``POST /_auth/admin-login`` | Checks the admin password, sets the cookie. |
| ``POST /_auth/logout`` | Ends this session (or all with ``everywhere=1``). |

The ``GET``/``POST`` split on the link matters: corporate mail scanners
(Outlook Safe Links and the like) fetch every link in an e-mail before the
user does. A link that signed in on ``GET`` would be used up — or used — by
the scanner.

Every ``POST`` must come from this app's own pages (``Origin`` check, with
``Sec-Fetch-Site`` as fallback); that and ``SameSite=Lax`` are the CSRF
defence. Redirect targets are same-origin paths only.
"""

from __future__ import annotations

import html
from urllib.parse import urlsplit

import reflex as rx
from reflex.config import get_config
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from ..navigation import routes
from . import security, service, settings
from .cookie import COOKIE_NAME, clear_session_cookie, set_session_cookie
from .state import ENDPOINT_PREFIX, frontend_url


def _origin(url: str | None) -> str:
    parts = urlsplit(url or "")
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


# ``form-action`` also governs where a form's POST may redirect to, so it
# must name the frontend origin: in development that is :3000, not 'self'.
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    # Not "no-referrer": with it, browsers send ``Origin: null`` on the
    # confirm form's POST. "same-origin" still keeps the token-bearing URL
    # from leaking to any other site.
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
        f"form-action 'self' {_origin(get_config().deploy_url)}; "
        "frame-ancestors 'none'; base-uri 'none'"
    ),
}


def _from_this_app(request: Request) -> bool:
    config = get_config()
    allowed = {_origin(config.api_url), _origin(config.deploy_url)} - {""}
    origin = request.headers.get("origin")
    if origin is not None and origin != "null":
        return origin in allowed
    # No usable Origin (some privacy settings send "null"): fall back to the
    # browser's own verdict. A sandboxed attacker iframe reports cross-site.
    return request.headers.get("sec-fetch-site") in ("same-origin", "same-site")


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else ""
    return security.client_ip(peer, request.headers.get("x-forwarded-for"))


def _redirect(path: str) -> RedirectResponse:
    response = RedirectResponse(frontend_url(path), status_code=303)
    response.headers.update(
        {k: v for k, v in _SECURITY_HEADERS.items() if k != "Content-Security-Policy"}
    )
    return response


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{html.escape(title)} · {html.escape(settings.APP_TITLE)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; display: grid; place-items: center;
         min-height: 100vh; margin: 0; background: #f8fafc; color: #0f172a; }}
  main {{ text-align: center; padding: 2rem; max-width: 26rem; }}
  button, a.button {{ font: inherit; padding: .7rem 1.6rem; border: 0; border-radius: .5rem;
           background: #2563eb; color: white; cursor: pointer; text-decoration: none; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #0f172a; color: #e2e8f0; }} }}
</style></head>
<body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>"""
    return HTMLResponse(document, status_code=status, headers=_SECURITY_HEADERS)


async def link_get(request: Request) -> Response:
    token = request.query_params.get("t", "")

    def peek() -> bool:
        with rx.session() as db:
            return bool(token) and service.peek_link(db, token)

    if not await run_in_threadpool(peek):
        login = html.escape(frontend_url(routes.LOGIN_ROUTE), quote=True)
        return _page(
            "Link expired",
            f'<p>This sign-in link was already used or has expired.</p><p><a class="button" href="{login}">Request a new one</a></p>',
            status=410,
        )
    return _page(
        f"Sign in to {settings.APP_TITLE}",
        f'<form method="post" action="{ENDPOINT_PREFIX}/link">'
        f'<input type="hidden" name="t" value="{html.escape(token, quote=True)}">'
        '<button type="submit">Sign in</button></form>',
    )


async def link_post(request: Request) -> Response:
    if not _from_this_app(request):
        return Response("Cross-site request refused.", status_code=403)
    form = await request.form()
    token = str(form.get("t", ""))
    ip, agent = _client_ip(request), request.headers.get("user-agent", "")

    def redeem() -> tuple[str, str] | None:
        with rx.session() as db:
            return service.redeem_link(db, token, client_ip=ip, user_agent=agent)

    result = await run_in_threadpool(redeem) if token else None
    if result is None:
        return _redirect(f"{routes.LOGIN_ROUTE}?error=link")
    session_token, redirect_to = result
    response = _redirect(security.safe_redirect_path(redirect_to, routes.HOME_ROUTE))
    set_session_cookie(response, session_token)
    return response


async def admin_login_post(request: Request) -> Response:
    if not _from_this_app(request):
        return Response("Cross-site request refused.", status_code=403)
    form = await request.form()
    email, password = str(form.get("email", "")), str(form.get("password", ""))
    redirect_to = security.safe_redirect_path(str(form.get("redirect_to", "")), routes.HOME_ROUTE)
    ip, agent = _client_ip(request), request.headers.get("user-agent", "")

    def login() -> tuple[str | None, service.AdminOutcome]:
        with rx.session() as db:
            return service.admin_login(db, email, password, client_ip=ip, user_agent=agent)

    token, outcome = await run_in_threadpool(login)
    if token is None:
        return _redirect(f"{routes.ADMIN_LOGIN_ROUTE}?error={outcome}")
    response = _redirect(redirect_to)
    set_session_cookie(response, token)
    return response


async def logout_post(request: Request) -> Response:
    if not _from_this_app(request):
        return Response("Cross-site request refused.", status_code=403)
    form = await request.form()
    everywhere = form.get("everywhere") == "1"
    raw = request.cookies.get(COOKIE_NAME, "")
    ip = _client_ip(request)

    def logout() -> None:
        if raw:
            with rx.session() as db:
                service.logout(db, security.token_hash(raw), everywhere=everywhere, client_ip=ip)

    await run_in_threadpool(logout)
    response = _redirect(routes.LOGIN_ROUTE)
    clear_session_cookie(response)
    return response


def auth_api() -> Starlette:
    """The ``api_transformer`` for ``rx.App``. Reflex mounts itself below it,
    so these routes take precedence and everything else falls through."""
    return Starlette(
        routes=[
            Route(f"{ENDPOINT_PREFIX}/link", link_get, methods=["GET"]),
            Route(f"{ENDPOINT_PREFIX}/link", link_post, methods=["POST"]),
            Route(f"{ENDPOINT_PREFIX}/admin-login", admin_login_post, methods=["POST"]),
            Route(f"{ENDPOINT_PREFIX}/logout", logout_post, methods=["POST"]),
        ]
    )
