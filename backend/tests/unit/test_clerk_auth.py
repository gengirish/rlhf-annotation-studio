"""Unit tests for Clerk session-token verification.

Signing keys are generated in-process, so these run without network access and
without a real Clerk instance.
"""

from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.config import get_settings
from app.services import clerk_auth
from app.services.clerk_auth import (
    ClerkAuthError,
    looks_like_clerk_token,
    verify_clerk_token,
)

ISSUER = "https://ideal-sponge-21.clerk.accounts.dev"
KID = "test-key-1"


@pytest.fixture(scope="module")
def rsa_key() -> dict:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return {"private": private_pem, "public": public_pem}


@pytest.fixture(autouse=True)
def _clerk_settings(monkeypatch, rsa_key):
    """Point settings at the fake issuer and stub the JWKS with our public key."""
    get_settings.cache_clear()
    monkeypatch.setenv("CLERK_ISSUER", ISSUER)
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret")

    jwks = {"keys": [{"kid": KID, "kty": "RSA", "alg": "RS256", "use": "sig"}]}

    async def fake_get(*, force: bool = False) -> dict:
        return jwks

    # jose accepts a PEM string as the key, so hand it the public PEM directly.
    monkeypatch.setattr(clerk_auth._jwks_cache, "get", fake_get)
    monkeypatch.setattr(
        clerk_auth, "_find_key", lambda _jwks, kid: rsa_key["public"] if kid == KID else None
    )
    yield
    get_settings.cache_clear()


def _token(rsa_key: dict, **overrides) -> str:
    claims = {
        "sub": "user_2abcXYZ",
        "iss": ISSUER,
        "email": "annotator@example.com",
        "name": "Test Annotator",
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
    }
    claims.update(overrides)
    return jwt.encode(claims, rsa_key["private"], algorithm="RS256", headers={"kid": KID})


# --- happy path ------------------------------------------------------------


async def test_verifies_valid_token_and_extracts_claims(rsa_key) -> None:
    claims = await verify_clerk_token(_token(rsa_key))
    assert claims.user_id == "user_2abcXYZ"
    assert claims.email == "annotator@example.com"
    assert claims.name == "Test Annotator"


async def test_missing_optional_claims_are_none(rsa_key) -> None:
    token = _token(rsa_key, email=None, name=None)
    claims = await verify_clerk_token(token)
    assert claims.user_id == "user_2abcXYZ"
    assert claims.email is None
    assert claims.name is None


# --- rejection paths -------------------------------------------------------


async def test_rejects_expired_token(rsa_key) -> None:
    token = _token(rsa_key, exp=int(time.time()) - 60)
    with pytest.raises(ClerkAuthError):
        await verify_clerk_token(token)


async def test_rejects_wrong_issuer(rsa_key) -> None:
    """A token from another Clerk instance must not authenticate here."""
    token = _token(rsa_key, iss="https://attacker.clerk.accounts.dev")
    with pytest.raises(ClerkAuthError):
        await verify_clerk_token(token)


async def test_rejects_token_signed_by_a_different_key() -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    forged = jwt.encode(
        {"sub": "user_evil", "iss": ISSUER, "exp": int(time.time()) + 600},
        other_pem,
        algorithm="RS256",
        headers={"kid": KID},
    )
    with pytest.raises(ClerkAuthError):
        await verify_clerk_token(forged)


async def test_rejects_unknown_key_id(rsa_key) -> None:
    token = jwt.encode(
        {"sub": "user_x", "iss": ISSUER, "exp": int(time.time()) + 600},
        rsa_key["private"],
        algorithm="RS256",
        headers={"kid": "not-a-real-kid"},
    )
    with pytest.raises(ClerkAuthError):
        await verify_clerk_token(token)


async def test_rejects_token_without_subject(rsa_key) -> None:
    token = _token(rsa_key, sub=None)
    with pytest.raises(ClerkAuthError):
        await verify_clerk_token(token)


async def test_rejects_garbage(rsa_key) -> None:
    with pytest.raises(ClerkAuthError):
        await verify_clerk_token("not-a-jwt")


# --- routing between Clerk and legacy tokens -------------------------------


def test_rs256_token_routes_to_clerk(rsa_key) -> None:
    assert looks_like_clerk_token(_token(rsa_key)) is True


def test_hs256_legacy_token_does_not_route_to_clerk() -> None:
    """Legacy tokens must keep working through the HS256 path."""
    legacy = jwt.encode({"sub": "some-uuid"}, "unit-test-secret", algorithm="HS256")
    assert looks_like_clerk_token(legacy) is False


def test_malformed_token_does_not_route_to_clerk() -> None:
    assert looks_like_clerk_token("garbage") is False
