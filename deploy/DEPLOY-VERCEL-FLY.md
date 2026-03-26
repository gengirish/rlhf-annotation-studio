# Deploy: Vercel CLI + Fly CLI

The UI is a static build in `out/` (Vercel). The API is FastAPI on Fly.io + Neon. Vercel rewrites `/api/*` to your Fly hostname.

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

Optional:

```bash
fly secrets set APP_ENV=production DEBUG=false
```

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

From the **repository root** (same folder as `vercel.json`). If you’re still inside `backend/`, run `cd ..` first.

```bash
node scripts/sync-vercel-fly-rewrite.mjs https://YOUR-APP.fly.dev
```

Commit `vercel.json` if you want this rewrite in git for future deploys.

---

## Part C — Vercel CLI (UI)

Run from the **repository root** (where `vercel.json` and `package.json` are).

### 1. Log in

```bash
vercel login
```

### 2. Link this folder to a Vercel project (first time)

```bash
vercel link
```

Answer prompts: scope (team/account), project name (e.g. `rlhf-annotation-studio`), link to existing project or create new.

### 3. Preview deploy (optional)

```bash
vercel
```

Opens a preview URL; good for testing before production.

### 4. Production deploy

```bash
vercel --prod
```

The CLI uses **`vercel.json`**: `buildCommand` (`npm run vercel-build`), `outputDirectory` (`out`), rewrites.

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
| Frontend | https://rlhf-annotation-frontend.vercel.app |
| Auth page | https://rlhf-annotation-frontend.vercel.app/auth |
| Dashboard | https://rlhf-annotation-frontend.vercel.app/dashboard |
| API (Fly, direct) | https://rlhf-annotation-api.fly.dev |
| API health (via Vercel rewrite) | https://rlhf-annotation-frontend.vercel.app/api/v1/health |
| Task packs catalog | https://rlhf-annotation-frontend.vercel.app/api/v1/tasks/packs |
| API interactive docs | https://rlhf-annotation-api.fly.dev/api/docs |

## Smoke test

1. Open the **Frontend** URL above (or copy from `vercel --prod` output).
2. Register or log in at `/auth`.
3. Dashboard should load task packs from the API — traffic goes to `/api/v1/tasks/packs` and is rewritten to Fly.
4. Verify API health: `curl https://rlhf-annotation-frontend.vercel.app/api/v1/health` should return `{"status":"ok"}`.

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

- Fly `min_machines_running = 0` in `fly.toml` allows scale-to-zero (cold starts).
- Neon free tier limits apply.
