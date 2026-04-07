from __future__ import annotations

import secrets
from datetime import UTC, datetime

import bcrypt

from app.models.api_key import APIKey

_RAW_PREFIX = "rlhf_"
_RANDOM_HEX_BYTES = 20


def generate_key() -> tuple[str, str, str]:
    """Return (raw_key, bcrypt_hash, key_prefix). Raw key is never stored."""
    raw_key = _RAW_PREFIX + secrets.token_hex(_RANDOM_HEX_BYTES)
    key_hash = bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


def verify_key(raw_key: str, key_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_key.encode("utf-8"), key_hash.encode("utf-8"))
    except ValueError:
        return False


def check_scope(key: APIKey, required_scope: str) -> bool:
    scopes = key.scopes or []
    if "admin" in scopes:
        return True
    return required_scope in scopes


def is_expired(key: APIKey) -> bool:
    if key.expires_at is None:
        return False
    now = datetime.now(UTC)
    exp = key.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    return now > exp
