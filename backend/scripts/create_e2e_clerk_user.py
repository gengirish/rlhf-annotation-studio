"""Create (or recreate) the dedicated Clerk user the Playwright suite signs in as.

Writes E2E_CLERK_USER into frontend/.env.local, which is gitignored.

Usage (from backend/):
    python scripts/create_e2e_clerk_user.py

Requires CLERK_SECRET_KEY in backend/.env or the repo-root .env.local.

Two details that are easy to get wrong:

* The address must end in ``+clerk_test@example.com``. Clerk treats these as
  test accounts — no mail is sent and a fixed verification code is accepted,
  which is what lets Playwright sign in unattended.
* Sign-in uses the ``email_code`` strategy, not ``password``. On a default Clerk
  instance ``password`` is enabled as an *attribute* but not as a *first
  factor*, so password sign-in fails silently. Check with:
  ``GET {frontend_api}/v1/environment`` → ``user_settings.attributes.password``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
FRONTEND_ENV = ROOT / "frontend" / ".env.local"
EMAIL = "e2e-playwright+clerk_test@example.com"
CLERK_API = "https://api.clerk.com/v1"


def read_env(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    match = re.search(rf"^\s*{key}\s*=\s*(.+?)\s*$", path.read_text(encoding="utf-8"), re.M)
    return match.group(1).strip("\"'") if match else None


def main() -> int:
    secret = read_env(BACKEND / ".env", "CLERK_SECRET_KEY") or read_env(
        ROOT / ".env.local", "CLERK_SECRET_KEY"
    )
    if not secret:
        print("CLERK_SECRET_KEY not found in backend/.env or .env.local", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    with httpx.Client(headers=headers, timeout=30.0) as client:
        existing = client.get(f"{CLERK_API}/users", params={"email_address": [EMAIL]})
        found = existing.json() if existing.status_code == 200 else []
        if isinstance(found, dict):
            found = found.get("data", [])

        if found:
            user_id = found[0]["id"]
            print(f"e2e user already exists: {user_id} <{EMAIL}>")
        else:
            response = client.post(
                f"{CLERK_API}/users",
                json={
                    "email_address": [EMAIL],
                    "first_name": "E2E",
                    "last_name": "Playwright",
                    "skip_password_checks": True,
                    "public_metadata": {"purpose": "automated-e2e"},
                },
            )
            if response.status_code not in (200, 201):
                print(
                    f"create failed: HTTP {response.status_code} {response.text[:400]}",
                    file=sys.stderr,
                )
                return 1
            user_id = response.json()["id"]
            print(f"created e2e user {user_id} <{EMAIL}>")

    current = read_env(FRONTEND_ENV, "E2E_CLERK_USER")
    if current == EMAIL:
        print("frontend/.env.local already points at this user")
    else:
        with FRONTEND_ENV.open("a", encoding="utf-8") as fh:
            fh.write("\n# Clerk user the Playwright suite signs in as (gitignored).\n")
            fh.write(f"E2E_CLERK_USER={EMAIL}\n")
        print("wrote E2E_CLERK_USER to frontend/.env.local")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
