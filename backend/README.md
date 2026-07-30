# RLHF Annotation API

FastAPI + **async SQLAlchemy** + **Neon PostgreSQL** backend for the RLHF Annotation Studio Next.js frontend.

## Quick start

1. **Python 3.11+**

2. **Install**
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -e .
   ```

3. **Configure Neon**
   - Copy `.env.example` → `.env` (never commit `.env`).
   - In Neon: copy the **pooled** connection string.
   - Convert to async URL for the app:
     - Replace `postgresql://` with `postgresql+asyncpg://`
     - Keep `?ssl=require` (or `sslmode=require` — SQLAlchemy/asyncpg usually accept both).

   Example:
   ```env
   DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@ep-xxx-pooler.ap-southeast-2.aws.neon.tech/neondb?ssl=require
   ```

   If you see errors about `channel_binding`, remove `&channel_binding=require` from the URL.

4. **Migrations**
   ```bash
   alembic upgrade head
   ```

5. **Run**
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   Open [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs).

## Connect the Next.js UI

1. Run the frontend app:
   ```
   cd ../frontend
   npm install
   npm run dev
   ```

2. Open:
   ```
   http://127.0.0.1:3000/sign-in
   ```

3. Sign up through Clerk once — the app creates a **work session** in Neon on first
   authenticated request and syncs workspace JSON on each save.

## API (v1)

### Auth

Sign-in is handled by **Clerk**. The frontend sends the Clerk session token as
`Authorization: Bearer <token>`; the API verifies it (RS256) against the
instance's public JWKS and maps it to an `Annotator` via `clerk_user_id`,
falling back to email so migrated accounts keep their history.

**Roles live in this database, not in Clerk.** `require_role` reads
`Annotator.role`; Clerk only establishes identity.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | **Legacy.** Superseded by Clerk sign-up; retained for the migration window |
| POST | `/api/v1/auth/login` | **Legacy.** Superseded by Clerk sign-in; retained for the migration window |

While `LEGACY_JWT_ENABLED=true`, the API accepts both Clerk (RS256) and legacy
(HS256) tokens, so no one is signed out mid-migration. Both are rate limited —
see [Rate limiting](#rate-limiting).

Move existing accounts across with `scripts/import_users_to_clerk.py`; it sends
the stored bcrypt digest to Clerk so passwords keep working.

### Sessions & Workspace
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/sessions/bootstrap` | Legacy bootstrap (no password) |
| GET | `/api/v1/sessions/{id}/workspace` | Load tasks, annotations, timings (JWT) |
| PUT | `/api/v1/sessions/{id}/workspace` | Save workspace snapshot (JWT) |
| GET | `/api/v1/sessions/{id}/workspace/history` | Last 20 workspace revisions (JWT) |

### Tasks
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tasks/packs` | List all task packs |
| GET | `/api/v1/tasks/packs/{slug}` | Full task pack with tasks_json |
| POST | `/api/v1/tasks/packs` | Create task pack (JWT) |
| PUT | `/api/v1/tasks/packs/{slug}` | Update task pack (JWT) |
| DELETE | `/api/v1/tasks/packs/{slug}` | Delete task pack (JWT) |
| POST | `/api/v1/tasks/validate` | Validate task array |
| POST | `/api/v1/tasks/score-session` | Score session against gold tasks (JWT) |

### Reviews (role-gated)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/reviews/queue` | Current user's assignments (JWT) |
| GET | `/api/v1/reviews/pending` | Submitted reviews awaiting approval (admin/reviewer) |
| GET | `/api/v1/reviews/team` | All team assignments, `?status=`/`?annotator_id=` filters (admin/reviewer) |
| POST | `/api/v1/reviews/assign` | Assign single task to annotator (admin/reviewer) |
| POST | `/api/v1/reviews/bulk-assign` | Assign entire task pack to annotator (admin/reviewer) |
| PUT | `/api/v1/reviews/{id}` | Approve/reject submission (admin/reviewer) |
| POST | `/api/v1/reviews/{id}/submit` | Annotator submits annotation (JWT, owner only) |

### Organizations
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/orgs` | Create org (creator becomes admin) |
| GET | `/api/v1/orgs/{id}` | Get org details (member) |
| PUT | `/api/v1/orgs/{id}` | Update org settings (admin only) |
| GET | `/api/v1/orgs/{id}/members` | List org members |
| POST | `/api/v1/orgs/{id}/members` | Add member by email |
| PUT | `/api/v1/orgs/{id}/members/{mid}/role` | Change member role (admin only) |
| GET | `/api/v1/orgs/{id}/team-stats` | Per-member annotation stats (admin/reviewer) |

### Metrics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/metrics/session/{id}/summary` | Session completion stats (JWT) |
| GET | `/api/v1/metrics/session/{id}/timeline` | Completion timeline (JWT) |

### Inference
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/inference/status` | Whether inference is enabled |
| GET | `/api/v1/inference/models` | Available HF models |
| POST | `/api/v1/inference/stream` | Live streaming completions (optional JWT) |
| POST | `/api/v1/inference/complete` | Multi-slot parallel completions (optional JWT) |

### Roles

Every annotator has a `role` column: `admin`, `reviewer`, or `annotator` (default).
- `annotator` — standard access: own queue, submit annotations
- `reviewer` — can assign tasks, approve/reject submissions, view team stats
- `admin` — can change roles, manage org settings, all reviewer capabilities
- Org creator is auto-promoted to admin; roles are changed via `PUT /orgs/{id}/members/{mid}/role`

### Hugging Face live responses

1. Create a [fine-grained token](https://huggingface.co/settings/tokens) with **Make calls to Inference Providers**.
2. In `.env`: `HF_API_TOKEN=hf_...` (or `HF_TOKEN`).
3. Optional: `HF_DEFAULT_MODEL`, `HF_ROUTER_BASE_URL` (default `https://router.huggingface.co/v1`).
4. In the UI, sign in and use the dashboard task flow. The frontend calls `/api/v1/inference/*` directly via `NEXT_PUBLIC_API_URL`.
5. Set `INFERENCE_REQUIRE_AUTH=true` if the API is public and you want to require a bearer token (Clerk or legacy) on inference routes.

## Environment

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Optional sync URL for Alembic (`postgresql+psycopg://...`). If omitted, `+asyncpg` is swapped to `+psycopg`. |
| `APP_ENV` | `production` enables fail-fast startup checks (see below) |
| `CORS_ORIGINS` | Comma-separated origins allowed for the browser UI |
| `ROOT_PATH` | Optional reverse-proxy subpath |
| `DEBUG` | `true` to echo SQL |
| `HF_API_TOKEN` / `HF_TOKEN` | Hugging Face token for Inference Providers router |
| `HF_DEFAULT_MODEL` | Default Hub model id for `/inference/complete` |
| `CLERK_ISSUER` | Clerk Frontend API origin; JWKS is read from `{issuer}/.well-known/jwks.json`. Empty disables the Clerk path |
| `CLERK_SECRET_KEY` | Backend API key — used **only** by the import script, never on the request path |
| `CLERK_PUBLISHABLE_KEY` | Public key, mirrors the frontend's `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` |
| `LEGACY_JWT_ENABLED` | `true` to keep accepting old HS256 tokens during the migration |
| `JWT_SECRET` | Secret for signing **legacy** tokens |
| `JWT_EXPIRE_MINUTES` | Legacy token expiration (default `1440` = 24h) |
| `JWT_ALGORITHM` | Legacy JWT algorithm (default `HS256`) |
| `INFERENCE_REQUIRE_AUTH` | `true` to require `Authorization: Bearer` on inference routes |
| `INFERENCE_MAX_TOKENS` | Max new tokens per completion (default `1024`) |
| `INFERENCE_TIMEOUT_SECONDS` | HTTP timeout to HF router (default `120`) |

### Startup guards

With `APP_ENV=production` the app refuses to boot rather than fail open:

- `JWT_SECRET` left at its default → abort (the default is public, so legacy
  tokens would be forgeable)
- `CORS_ORIGINS` empty or `*` → abort (any site could otherwise drive the API)

### Rate limiting

In-process sliding windows, keyed on the real client IP taken from
`Fly-Client-IP` / `X-Forwarded-For` — which requires uvicorn to run with
`--proxy-headers` (set in the `Dockerfile`). Without it every caller shares the
proxy's address and the limit becomes global.

| Scope | Limit |
|-------|-------|
| `POST /api/v1/inference/*` | 30 per 60s per client |
| `POST /api/v1/auth/login`, `/register` | 10 per 300s per client |

State is **per process**. Running more than one machine multiplies the effective
limit; move to a shared store (e.g. Redis) before scaling out.
