"""Verification of Clerk session tokens.

Clerk signs session JWTs with RS256 and publishes the public keys at
``{issuer}/.well-known/jwks.json``. We fetch that key set, cache it, and verify
tokens locally — no network round-trip to Clerk per request.

Only the public JWKS is needed here. ``CLERK_SECRET_KEY`` is for Backend API
calls (see ``scripts/import_users_to_clerk.py``) and is deliberately not used
on the request path.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger("app.clerk")


class ClerkAuthError(Exception):
    """Raised when a token is absent, malformed, expired, or not from Clerk."""


@dataclass
class ClerkClaims:
    """The subset of Clerk's session claims this app relies on."""

    user_id: str
    email: str | None
    name: str | None
    org_id: str | None


class _JwksCache:
    """Caches the JWKS and refreshes on expiry or on an unknown key id.

    An unknown `kid` usually means Clerk rotated its signing key, so we allow a
    single forced refresh per verification attempt rather than failing outright.
    """

    def __init__(self) -> None:
        self._keys: dict | None = None
        self._fetched_at: float = 0.0

    def _expired(self, ttl: float) -> bool:
        return self._keys is None or (time.time() - self._fetched_at) > ttl

    async def get(self, *, force: bool = False) -> dict:
        settings = get_settings()
        if not settings.clerk_enabled:
            raise ClerkAuthError("Clerk is not configured (CLERK_ISSUER is unset)")

        if force or self._expired(settings.clerk_jwks_cache_seconds):
            url = settings.clerk_jwks_url
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    self._keys = response.json()
                    self._fetched_at = time.time()
            except (httpx.HTTPError, ValueError) as exc:
                # Serve a stale key set rather than locking everyone out over a
                # transient blip; only hard-fail if we have nothing cached.
                if self._keys is not None:
                    logger.warning("JWKS refresh from %s failed, using cached keys: %s", url, exc)
                else:
                    raise ClerkAuthError(f"Could not fetch Clerk JWKS: {exc}") from exc

        assert self._keys is not None
        return self._keys

    def clear(self) -> None:
        self._keys = None
        self._fetched_at = 0.0


_jwks_cache = _JwksCache()


def _find_key(jwks: dict, kid: str | None) -> dict | None:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def verify_clerk_token(token: str) -> ClerkClaims:
    """Verify a Clerk session JWT and return its claims.

    Raises ``ClerkAuthError`` for anything that should read as a 401.
    """
    settings = get_settings()
    if not settings.clerk_enabled:
        raise ClerkAuthError("Clerk is not configured")

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise ClerkAuthError("Malformed token") from exc

    kid = header.get("kid")
    jwks = await _jwks_cache.get()
    key = _find_key(jwks, kid)
    if key is None:
        # Likely a key rotation — refetch once before giving up.
        jwks = await _jwks_cache.get(force=True)
        key = _find_key(jwks, kid)
    if key is None:
        raise ClerkAuthError("Token signed with an unknown key")

    issuer = settings.clerk_issuer.rstrip("/")
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            # Clerk session tokens carry no `aud`; the issuer check plus the
            # signature is what binds the token to this Clerk instance.
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise ClerkAuthError(f"Invalid Clerk token: {exc}") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise ClerkAuthError("Clerk token has no subject")

    return ClerkClaims(
        user_id=user_id,
        email=_first_str(claims, "email", "primary_email_address", "email_address"),
        name=_first_str(claims, "name", "full_name", "username"),
        org_id=_first_str(claims, "org_id"),
    )


def _first_str(claims: dict, *names: str) -> str | None:
    """Return the first claim present as a non-empty string.

    Clerk's default session claims are minimal and the exact names depend on the
    instance's JWT template, so several spellings are tolerated.
    """
    for name in names:
        value = claims.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


CLERK_API = "https://api.clerk.com/v1"


async def fetch_clerk_user(user_id: str) -> tuple[str | None, str | None]:
    """Look up a Clerk user's primary email and name via the Backend API.

    Clerk's default session token carries only `sub`, `iss`, `sid` and friends —
    **no email** unless a custom JWT template adds one. Provisioning a local
    annotator needs an email, so fall back to asking Clerk directly rather than
    requiring every deployment to configure a JWT template correctly.

    Returns ``(email, name)``; either may be None if Clerk is unreachable.
    """
    settings = get_settings()
    if not settings.clerk_secret_key:
        logger.warning("CLERK_SECRET_KEY is unset; cannot resolve user %s", user_id)
        return (None, None)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{CLERK_API}/users/{user_id}",
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Clerk user lookup failed for %s: %s", user_id, exc)
        return (None, None)

    # Prefer the address flagged primary; fall back to the first verified one.
    primary_id = data.get("primary_email_address_id")
    addresses = data.get("email_addresses") or []
    email = None
    for entry in addresses:
        if entry.get("id") == primary_id:
            email = entry.get("email_address")
            break
    if not email and addresses:
        email = addresses[0].get("email_address")

    name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p) or None
    return (email, name)


def looks_like_clerk_token(token: str) -> bool:
    """Cheap RS256-header check used to pick a verification path.

    Legacy tokens are HS256; Clerk's are RS256. This only routes the attempt —
    it is not a security check, since both paths verify signatures.
    """
    try:
        return jwt.get_unverified_header(token).get("alg", "").upper().startswith("RS")
    except JWTError:
        return False
