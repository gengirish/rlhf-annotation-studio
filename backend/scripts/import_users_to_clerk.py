"""One-off import of existing annotators into Clerk, preserving passwords.

Clerk accepts an existing bcrypt digest via `password_digest` + `password_hasher`,
so migrated users sign in with the credentials they already have — no reset
emails, no lockout.

The script is idempotent: annotators that already carry a `clerk_user_id` are
skipped, so it is safe to re-run after a partial failure.

Usage (from backend/):
    python scripts/import_users_to_clerk.py --dry-run     # report only
    python scripts/import_users_to_clerk.py               # perform the import

Requires CLERK_SECRET_KEY and DATABASE_URL in backend/.env.

Verified against Clerk's Backend API spec (POST /v1/users): `email_address` is an
array, the digest fields are `password_digest` / `password_hasher`, and `bcrypt`
is a supported hasher.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

# Running this file directly puts `scripts/` on sys.path, not `backend/`, so the
# `app` package would not resolve unless it happens to be pip-installed. Add the
# backend root explicitly so `python scripts/import_users_to_clerk.py` works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models.annotator import Annotator  # noqa: E402

CLERK_API = "https://api.clerk.com/v1"

# Clerk rate-limits user creation; stay well under it rather than racing and
# retrying. ~3 users/second is ample for a one-off import of this size.
DELAY_BETWEEN_USERS = 0.35
MAX_RETRIES = 5

# Accounts left behind by the e2e/benchmark suites. Clerk bills per active user,
# so importing these is pure noise — but skipping is opt-in, since only the
# project owner can say which addresses are genuinely disposable.
TEST_ACCOUNT_PATTERN = re.compile(
    r"(^|[-_.])(e2e|bench|smoke|dummy|fake|load)([-_.0-9]|@)|@(test|example)\.(com|invalid)",
    re.I,
)


def is_test_account(email: str) -> bool:
    return bool(TEST_ACCOUNT_PATTERN.search(email or ""))


def split_name(full_name: str) -> tuple[str, str | None]:
    parts = (full_name or "").strip().split()
    if not parts:
        return ("User", None)
    if len(parts) == 1:
        return (parts[0], None)
    return (parts[0], " ".join(parts[1:]))


async def create_clerk_user(client: httpx.AsyncClient, annotator: Annotator) -> str:
    """Create one Clerk user and return its id, retrying on rate limits."""
    first_name, last_name = split_name(annotator.name)
    payload: dict = {
        "external_id": str(annotator.id),
        "email_address": [annotator.email],
        "first_name": first_name,
        # Role stays authoritative in our DB; this copy is for readability in
        # the Clerk dashboard only.
        "public_metadata": {"role": annotator.role},
        # Imported digests can trip "password found in a breach" checks, which
        # would reject otherwise-valid existing accounts.
        "skip_password_checks": True,
    }
    if last_name:
        payload["last_name"] = last_name
    if annotator.password_hash:
        payload["password_digest"] = annotator.password_hash
        payload["password_hasher"] = "bcrypt"

    for attempt in range(1, MAX_RETRIES + 1):
        response = await client.post(f"{CLERK_API}/users", json=payload)

        if response.status_code in (200, 201):
            return response.json()["id"]

        if response.status_code == 429:
            wait = float(response.headers.get("Retry-After", 2 ** attempt))
            print(f"    rate limited, waiting {wait:.0f}s (attempt {attempt}/{MAX_RETRIES})")
            await asyncio.sleep(wait)
            continue

        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

    raise RuntimeError("gave up after repeated rate limiting")


async def find_existing_clerk_user(client: httpx.AsyncClient, email: str) -> str | None:
    """Return the Clerk id for an email if it is already present.

    Makes a re-run safe even when a previous attempt created the Clerk user but
    died before writing `clerk_user_id` back to our database.
    """
    response = await client.get(f"{CLERK_API}/users", params={"email_address": [email]})
    if response.status_code != 200:
        return None
    users = response.json()
    if isinstance(users, dict):  # some API versions wrap the list
        users = users.get("data", [])
    return users[0]["id"] if users else None


async def main(dry_run: bool, skip_test_accounts: bool) -> int:
    settings = get_settings()
    if not settings.clerk_secret_key:
        print("CLERK_SECRET_KEY is not set (add it to backend/.env)", file=sys.stderr)
        return 2

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:  # type: AsyncSession
        result = await db.execute(select(Annotator).order_by(Annotator.created_at))
        annotators = list(result.scalars().all())

        already_linked = [a for a in annotators if a.clerk_user_id]
        unlinked = [a for a in annotators if not a.clerk_user_id]
        looks_test = [a for a in unlinked if is_test_account(a.email)]
        pending = [a for a in unlinked if not is_test_account(a.email)] if skip_test_accounts \
            else unlinked
        with_password = [a for a in pending if a.password_hash]

        test_note = " (SKIPPED)" if skip_test_accounts else " (--skip-test-accounts to omit)"
        print(f"annotators total          : {len(annotators)}")
        print(f"already linked to Clerk   : {len(already_linked)}")
        print(f"look like test accounts   : {len(looks_test)}{test_note}")
        print(f"to import                 : {len(pending)}")
        print(f"  ...with a password hash : {len(with_password)}")
        print(f"  ...without (no password): {len(pending) - len(with_password)}")

        if dry_run:
            print("\n--dry-run: nothing was written. Sample of what would be sent:")
            for a in pending[:5]:
                first, last = split_name(a.name)
                digest = "bcrypt digest" if a.password_hash else "NO PASSWORD (invite flow)"
                print(f"  {a.email:38} {first} {last or ''} [{a.role}] <- {digest}")
            return 0

        if not pending:
            print("\nNothing to do.")
            return 0

        headers = {
            "Authorization": f"Bearer {settings.clerk_secret_key}",
            "Content-Type": "application/json",
        }
        imported = skipped = failed = 0

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            for annotator in pending:
                try:
                    existing = await find_existing_clerk_user(client, annotator.email)
                    if existing:
                        annotator.clerk_user_id = existing
                        await db.commit()
                        print(f"  = {annotator.email:38} already in Clerk, linked")
                        skipped += 1
                        continue

                    clerk_id = await create_clerk_user(client, annotator)
                    annotator.clerk_user_id = clerk_id
                    await db.commit()
                    print(f"  + {annotator.email:38} -> {clerk_id}")
                    imported += 1
                except Exception as exc:  # keep going; report at the end
                    await db.rollback()
                    print(f"  ! {annotator.email:38} FAILED: {exc}", file=sys.stderr)
                    failed += 1

                await asyncio.sleep(DELAY_BETWEEN_USERS)

        print(f"\nimported={imported} linked-existing={skipped} failed={failed}")

    await engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would happen without calling Clerk or writing to the DB",
    )
    parser.add_argument(
        "--skip-test-accounts",
        action="store_true",
        help="omit e2e/bench/test-looking addresses (they bill as Clerk users)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run, args.skip_test_accounts)))
