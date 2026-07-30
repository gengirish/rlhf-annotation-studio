# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

Monorepo with three deployable/publishable pieces:

| Path | What | Deployed to |
|------|------|-------------|
| `frontend/` | Next.js 15 App Router, React 19, TypeScript | Vercel |
| `backend/` | FastAPI + SQLAlchemy async + Neon Postgres | Fly.io (`rlhf-annotation-api`, region `syd`) |
| `sdk/` | `rlhf-studio` Python client + `rlhf` CLI | PyPI-style package |

`docker/docker-compose.yml` runs the whole stack locally (postgres, redis, backend, frontend).

## Commands

Backend work uses the venv at `backend/.venv` (gitignored). Create it with
`python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"`.

```bash
# Backend (from backend/)
.venv/Scripts/python -m pytest -q                       # full suite
.venv/Scripts/python -m pytest tests/unit/test_x.py -q  # one file
.venv/Scripts/python -m pytest -k "test_name" -q        # one test
.venv/Scripts/python -m ruff check app tests            # lint
.venv/Scripts/python -m alembic upgrade head            # migrate
.venv/Scripts/python -m alembic current                 # current revision

# Frontend (from frontend/)
npm run dev | build | lint
npm test                                                # vitest run
npx vitest run tests/unit/some.test.ts                  # one file
npm run test:e2e                                        # playwright

# Root convenience wrappers
npm run frontend:dev | frontend:build | backend:test | test:all
```

## Known-failing baselines

Do not treat these as regressions you caused — verify against a clean tree before
assuming otherwise:

- **14 backend test failures** (13 in `tests/routers/test_tasks.py` asserting
  `401 == 200`, 3 errors in `tests/unit/test_audit_service.py`). Pre-existing.
- **~218 ruff errors** from `ruff check .` over `backend/`, mostly `E501` in
  `alembic/versions/`. This fails the CI `backend` job and blocks the entire
  `Deploy Backend (Fly.io)` workflow, which has been red since April — the Fly
  deploy step is never reached. Backend deploys are done manually with
  `fly deploy` from `backend/`.

## Architecture

### Auth (Clerk, with a legacy transition window)

Identity is Clerk; **authorization is not**. `Annotator.role` in Postgres is the
source of truth for `require_role` and its ~125 call sites — Clerk only proves
who the user is.

Request path:

1. `frontend/src/lib/api.ts` → `request()` is the single place a bearer token is
   attached. It reads `window.Clerk.session.getToken()`, falling back to the
   legacy `localStorage` token. Changing the token source here covers all ~20
   calling components; do not thread auth through them individually.
2. `backend/app/auth.py` → `get_annotator_from_bearer_token()` routes on the JWT
   header: RS256 → Clerk, HS256 → legacy. Every protected route funnels through
   this, `get_current_user_or_api_key`, or `require_role`.
3. `backend/app/services/clerk_auth.py` verifies RS256 against the instance JWKS
   (cached, force-refreshed once on an unknown `kid` to survive key rotation) and
   checks the `iss` claim. `CLERK_SECRET_KEY` is never used on the request path.

Clerk users map to annotators by `clerk_user_id`, then by **email** (which links
pre-migration accounts on first sign-in, preserving annotations/role/org), then
by just-in-time creation — which must also create a `WorkSession`, since
`/dashboard` assumes one exists.

`LEGACY_JWT_ENABLED=true` keeps HS256 tokens working. Before flipping it off:
`SELECT count(*) FROM annotators WHERE clerk_user_id IS NULL;`

`backend/scripts/import_users_to_clerk.py` migrates existing accounts with their
bcrypt digests (no password resets). Idempotent; `--dry-run` and
`--skip-test-accounts` supported.

### Next.js version constraints

The app is on **Next 15**, where the request-interception convention is
`middleware.ts`. Next 16 renamed it to `proxy.ts`. Creating a `proxy.ts` here is
silently ignored — it does not error, it just leaves every protected route open.
`frontend/src/middleware.ts` must stay named that.

`typedRoutes` is a top-level `next.config.mjs` key (moved out of `experimental`
in 15). It makes `redirect("/some-route")` a type error for catch-all segments;
cast with `as Route` from `next`.

`next lint` is deprecated and removed in Next 16 — a future upgrade needs
`npx @next/codemod@canary next-lint-to-eslint-cli .`.

### Frontend/backend boundary

The frontend never calls Fly directly in production. `frontend/vercel.json`
rewrites `/api/:path*` to the Fly hostname, so the browser sees same-origin
requests and `NEXT_PUBLIC_API_URL` stays empty. `scripts/sync-vercel-fly-rewrite.mjs`
rewrites that rule when the Fly hostname changes.

**The Vercel project's Root Directory is `frontend/`.** CLI commands need
`--cwd frontend`, `.vercel/` lives there, and there is deliberately no root
`vercel.json` — CLI 58 rejects top-level build settings once it detects
`frontend`/`backend` as separate services.

State is Zustand (`frontend/src/lib/state/store.ts`) plus TanStack Query;
`src/app/providers.tsx` holds the client providers, nested inside `ClerkProvider`
in `layout.tsx`.

### Backend request pipeline

`create_app()` in `backend/app/main.py` composes, in order: request-id header,
timing header, CORS, rate limiting, then a catch-all exception handler that logs
with the request id and returns it to the client. All routers mount under
`/api/v1`.

Rate limiting (`app/middleware/rate_limit.py`) keys on the real client IP from
`Fly-Client-IP`/`X-Forwarded-For`, which **requires uvicorn to run with
`--proxy-headers`** (set in `backend/Dockerfile`). Without it every request
carries Fly's proxy address and the per-client limit silently becomes global.
State is per-process — more than one machine multiplies every limit.

With `APP_ENV=production` the app refuses to start on a default `JWT_SECRET` or
a wildcard `CORS_ORIGINS` rather than failing open.

### Migrations

Alembic revisions in `backend/alembic/versions/` use sequential string ids
(`022_add_annotator_clerk_user_id`), not hashes, and each declares
`down_revision` explicitly. The Fly container runs `alembic upgrade head` plus
`seed_task_packs.py` on boot, so a bad migration takes the API down with it.

## Docs worth reading before changing deploy behaviour

`deploy/DEPLOY-VERCEL-FLY.md` (exact CLI workflow and required secrets),
`CICD.md`, and the "Production hardening" / "Authentication (Clerk)" sections of
`README.md`.
