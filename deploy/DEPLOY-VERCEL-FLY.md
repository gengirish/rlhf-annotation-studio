# Deploy: Vercel CLI + Fly CLI

The UI is a Next.js standalone build deployed on Vercel. The API is FastAPI on Fly.io + Neon. Vercel rewrites `/api/*` to your Fly hostname.

---

## Install the CLIs

### Fly.io (`fly`)

- **Windows (PowerShell):** `powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"`
- **macOS / Linux:** `curl -L https://fly.io/install.sh | sh`

Verify: `fly version`

### Vercel (`vercel`)

```bash
npm install -g vercel
```

Verify: `vercel --version`

---

## Part A — Fly.io (API)

Run these from a terminal. Database URL = your **Neon** string (use quotes; never commit it).

### 1. Log in

```bash
fly auth login
```

### 2. Create / configure the app (from `backend/`)

`fly.toml` and `Dockerfile` already live in **`backend/`**.

```bash
cd backend
```

**First time only** — register the app on Fly (reuse existing config when prompted):

```bash
fly launch
```

- Choose **deploy now: No** if you want to set secrets before the first deploy (recommended), or **Yes** if you’ll set `DATABASE_URL` immediately after.
- If asked, confirm region, accept the name in `fly.toml` (`rlhf-annotation-api`) or rename the `app` key in `fly.toml` first, then run `fly launch` again.

**Alternative (CLI-only, no wizard questions):** after editing `app` in `fly.toml`:

```bash
fly apps create rlhf-annotation-api --org personal
```

(Replace `rlhf-annotation-api` and `personal` with your app name and Fly org slug. List orgs: `fly orgs list`.)

### 3. Set secrets (required before a healthy deploy)

```bash
fly secrets set DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST/DB?sslmode=require"
```

Clerk (required for sign-in; `CLERK_ISSUER` is your Clerk Frontend API origin):

```bash
fly secrets set CLERK_ISSUER="https://YOUR-INSTANCE.clerk.accounts.dev" \
                CLERK_SECRET_KEY="sk_live_..." \
                LEGACY_JWT_ENABLED=true
```

`LEGACY_JWT_ENABLED=true` keeps old HS256 tokens working during the migration.
Set it to `false` once every annotator has a `clerk_user_id`.

Optional:

```bash
fly secrets set APP_ENV=production DEBUG=false
```

`APP_ENV=production` makes the API refuse to boot on a default `JWT_SECRET` or a
wildcard `CORS_ORIGINS`, rather than failing open. Set both before enabling it.

**PowerShell tip:** If the URL has `&` or other special characters, use single quotes for the outer string or escape carefully.

### 4. Deploy and check

```bash
fly deploy
fly status
fly logs
```

Open the app in browser (prints URL):

```bash
fly open
```

Or hit health directly (replace hostname):

```bash
curl https://rlhf-annotation-api.fly.dev/api/v1/health
```

Note your **HTTPS origin**, e.g. `https://rlhf-annotation-api.fly.dev` — you need it for Vercel’s rewrite.

### Useful Fly CLI commands

| Command | Purpose |
|--------|---------|
| `fly apps list` | Your apps |
| `fly secrets list` | Secret names (values hidden) |
| `fly ssh console` | Shell inside a machine |
| `fly scale count 1` | Keep one machine warm (optional, costs more) |
| `fly machine restart` | Bounce machines after config changes |

---

## Part B — Point Vercel at Fly

Vercel must proxy `/api/*` to `https://<your-app>.fly.dev/api/*`.

From the **repository root**. If you’re still inside `backend/`, run `cd ..` first.

```bash
node scripts/sync-vercel-fly-rewrite.mjs https://YOUR-APP.fly.dev
```

This rewrites the `/api/:path*` rule in **`frontend/vercel.json`**. Commit that file if you
want the rewrite in git for future deploys.

---

## Part C — Vercel CLI (UI)

The Vercel project's **Root Directory is `frontend/`**, so the CLI is linked there. Either
`cd frontend` first, or pass `--cwd frontend` to each command as shown below.

### 1. Log in

```bash
vercel login
```

### 2. Link this folder to a Vercel project (first time)

```bash
vercel link --cwd frontend
```

Answer prompts: scope (team/account), project name (e.g. `rlhf-annotation-studio`), link to existing project or create new.

### 3. Set the Clerk environment variable

The frontend needs Clerk's publishable key at build time. It is public by
design, so it is safe in the Vercel dashboard and in `.env.local`.

```bash
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --cwd frontend
```

Only the publishable key belongs here — `CLERK_SECRET_KEY` is a backend secret
and lives on Fly.

### 4. Preview deploy (optional)

```bash
vercel deploy --cwd frontend
```

Opens a preview URL; good for testing before production.

### 5. Production deploy

```bash
vercel deploy --prod --cwd frontend
```

Next.js is auto-detected, so no build overrides are needed. **`frontend/vercel.json`** supplies
only the `/api/:path*` rewrite to Fly and the `Cache-Control` header.

### Useful Vercel CLI commands

| Command | Purpose |
|--------|---------|
| `vercel ls` | Recent deployments |
| `vercel inspect <url>` | Build/deployment details |
| `vercel domains ls` | Domains on the project |
| `vercel env ls` | Project env vars (static site may need none) |
| `vercel pull` | Download project settings / env to `.vercel/` (optional) |

---

## Current Production URLs

| Service | URL |
|---------|-----|
| Frontend | https://rlhf-annotation-studio.vercel.app |
| Sign in (Clerk) | https://rlhf-annotation-studio.vercel.app/sign-in |
| Dashboard | https://rlhf-annotation-studio.vercel.app/dashboard |
| API (Fly, direct) | https://rlhf-annotation-api.fly.dev |
| API health (via Vercel rewrite) | https://rlhf-annotation-studio.vercel.app/api/v1/health |
| Task packs catalog | https://rlhf-annotation-studio.vercel.app/api/v1/tasks/packs |
| API interactive docs | https://rlhf-annotation-api.fly.dev/api/docs |

> `rlhf-studio.intelliforge.tech` currently 404s — the apex `intelliforge.tech`
> sits under a different Vercel scope, so `vercel domains add` returns
> `domain_not_owned`. DNS already CNAMEs to Vercel; attach the subdomain from the
> owning account and it goes live with no DNS change.

## Smoke test

1. Open the **Frontend** URL above (or copy from `vercel --prod` output).
2. Sign in through Clerk at `/sign-in`.
3. Dashboard should load task packs from the API — traffic goes to `/api/v1/tasks/packs` and is rewritten to Fly.
4. Verify API health: `curl https://rlhf-annotation-studio.vercel.app/api/v1/health` should return `{"status":"ok"}`.

---

## Troubleshooting

| Issue | CLI checks |
|--------|------------|
| API 502 / timeout | `fly status` · `fly logs` · `curl https://YOUR-APP.fly.dev/api/v1/health` |
| Wrong Fly host | Re-run `node scripts/sync-vercel-fly-rewrite.mjs https://...` then `vercel --prod` |
| Build fails on Vercel | `vercel --prod` locally and read logs; run `npm run vercel-build` locally |
| DB errors | `fly secrets list` · Neon firewall / `sslmode=require` |

---

## Cost notes

- Fly `min_machines_running = 1` in `fly.toml` keeps one machine warm (no cold starts, small always-on cost). Set it to `0` to allow scale-to-zero.
- Neon free tier limits apply.
