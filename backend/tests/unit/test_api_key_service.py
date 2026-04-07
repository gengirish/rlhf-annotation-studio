from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.api_key import APIKey
from app.services.api_key_service import (
    check_scope,
    generate_key,
    is_expired,
    verify_key,
)


def test_generate_key_format() -> None:
    raw, key_hash, prefix = generate_key()
    assert raw.startswith("rlhf_")
    assert len(raw) == 5 + 40
    assert len(prefix) == 8
    assert raw[:8] == prefix
    assert key_hash
    assert raw.encode("utf-8") != key_hash.encode("utf-8")


def test_verify_key_accepts_correct_key() -> None:
    raw, key_hash, _prefix = generate_key()
    assert verify_key(raw, key_hash) is True


def test_verify_key_rejects_wrong_key() -> None:
    raw, key_hash, _prefix = generate_key()
    wrong = "rlhf_" + "0" * 40
    assert raw != wrong
    assert verify_key(wrong, key_hash) is False


def test_is_expired_never_when_no_expiry() -> None:
    key = APIKey(
        name="t",
        key_hash="x",
        key_prefix="rlhf_aaa",
        scopes=["read"],
        expires_at=None,
    )
    assert is_expired(key) is False


def test_is_expired_true_when_past() -> None:
    key = APIKey(
        name="t",
        key_hash="x",
        key_prefix="rlhf_aaa",
        scopes=["read"],
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert is_expired(key) is True


def test_is_expired_false_when_future() -> None:
    key = APIKey(
        name="t",
        key_hash="x",
        key_prefix="rlhf_aaa",
        scopes=["read"],
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert is_expired(key) is False


@pytest.mark.parametrize(
    ("scopes", "required", "expected"),
    [
        (["read", "write"], "read", True),
        (["read", "write"], "write", True),
        (["read"], "write", False),
        (["admin"], "write", True),
        ([], "read", False),
    ],
)
def test_check_scope(scopes: list[str], required: str, expected: bool) -> None:
    key = APIKey(
        name="t",
        key_hash="x",
        key_prefix="rlhf_aaa",
        scopes=scopes,
    )
    assert check_scope(key, required) is expected
