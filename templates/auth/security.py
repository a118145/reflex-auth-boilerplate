"""Pure security helpers. No database, no Reflex — unit-testable as is."""

import base64
import functools
import hashlib
import hmac
import ipaddress
import secrets
from urllib.parse import urlsplit

from . import settings

# scrypt cost. 2**17 x 8 x 1 uses 128 MiB per hash (OWASP's recommendation).
# The parameters are stored inside each hash, so raising them later only
# affects newly generated hashes.
_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 256 * 1024 * 1024
# The encoded hash uses ":" separators, never "$": docker compose and most
# .env loaders interpolate "$..." and would silently mangle the value.


def new_token() -> str:
    """A 256-bit URL-safe random token (link or session)."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def email_hash(email: str) -> str:
    """Digest for logs and audit rows about addresses with no account."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def normalize_email(email: str) -> str | None:
    """Lower-cased address, or ``None`` if it is not plausibly one."""
    email = email.strip().lower()
    local, _, domain = email.rpartition("@")
    if not local or "." not in domain or any(c.isspace() for c in email) or len(email) > 254:
        return None
    return email


def domain_allowed(email: str) -> bool:
    return email.rpartition("@")[2] in settings.ALLOWED_DOMAINS


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
    )
    b64 = base64.b64encode
    return f"scrypt:{_SCRYPT_N}:{_SCRYPT_R}:{_SCRYPT_P}:{b64(salt).decode()}:{b64(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = encoded.split(":")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=_SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


@functools.cache
def dummy_password_hash() -> str:
    """Verified against on admin logins for an unknown address, so a wrong
    e-mail costs the same time as a wrong password and response timing does
    not reveal which. Built on first use, not at import."""
    return hash_password(secrets.token_hex(16))


def safe_redirect_path(target: str | None, fallback: str) -> str:
    """Accept only a same-origin absolute path; anything else is ``fallback``.

    Rejects scheme-relative (``//evil.test``), backslash (``/\\evil.test``,
    which browsers treat as ``//``), absolute URLs, control characters, and the
    backend's own ``/_auth`` routes.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return fallback
    if "\\" in target or any(ord(c) < 0x20 or ord(c) == 0x7F for c in target):
        return fallback
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return fallback
    if parts.path == "/_auth" or parts.path.startswith("/_auth/"):
        return fallback
    return target


def client_ip(peer: str, forwarded_for: str | None) -> str:
    """The client address, believing ``X-Forwarded-For`` only from a trusted proxy.

    Walks the header right to left and returns the first hop that is not a
    trusted proxy, so a client cannot spoof its address by sending the header
    itself.
    """
    if peer not in settings.TRUSTED_PROXIES or not forwarded_for:
        return peer
    hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
    for hop in reversed(hops):
        try:
            ipaddress.ip_address(hop)
        except ValueError:
            return peer
        if hop not in settings.TRUSTED_PROXIES:
            return hop
    return peer
