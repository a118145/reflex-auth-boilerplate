"""Microsoft Graph transport: send as a company mailbox via ``sendMail``.

Uses the OAuth client-credentials flow, so no user password is involved.

Setup in Entra ID (Azure AD):

1. Register an app; create a client secret.
2. API permissions → Microsoft Graph → **Application** permission
   ``Mail.Send``; grant admin consent.
3. Restrict the app to the one sending mailbox (otherwise ``Mail.Send`` can
   send as *any* mailbox in the tenant), e.g. with an Exchange
   ``New-ApplicationAccessPolicy -AccessRight RestrictAccess`` or RBAC for
   Applications.

| Variable | Meaning |
| --- | --- |
| ``GRAPH_TENANT_ID`` | Directory (tenant) id |
| ``GRAPH_CLIENT_ID`` | Application (client) id |
| ``GRAPH_CLIENT_SECRET`` | Client secret value |
| ``GRAPH_SENDER`` | Mailbox to send as, e.g. ``noreply@company.com`` |
"""

import threading
import time
from urllib.parse import quote

import httpx

from .message import MailMessage, env

_lock = threading.Lock()
_token: tuple[str, float] | None = None  # (access token, expiry as monotonic time)


def _access_token() -> str:
    global _token
    with _lock:
        if _token is not None and _token[1] > time.monotonic() + 60:
            return _token[0]
        response = httpx.post(
            f"https://login.microsoftonline.com/{quote(env('GRAPH_TENANT_ID'))}/oauth2/v2.0/token",
            data={
                "client_id": env("GRAPH_CLIENT_ID"),
                "client_secret": env("GRAPH_CLIENT_SECRET"),
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        _token = (str(payload["access_token"]), time.monotonic() + float(payload["expires_in"]))
        return _token[0]


def send(message: MailMessage) -> None:
    response = httpx.post(
        f"https://graph.microsoft.com/v1.0/users/{quote(env('GRAPH_SENDER'))}/sendMail",
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={
            "message": {
                "subject": message.subject,
                "body": {"contentType": "HTML", "content": message.html},
                "toRecipients": [{"emailAddress": {"address": message.to}}],
            },
            "saveToSentItems": False,
        },
        timeout=15,
    )
    response.raise_for_status()
