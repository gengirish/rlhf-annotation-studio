# CI/CD Strategy — RLHF Annotation Studio

## Pipeline Overview

```
PR opened ──► CI checks (parallel) ──► Preview deploy ──► Review
                                                            │
master push ──► CI checks ──► Deploy Backend (Fly.io) ──► Deploy Frontend (Vercel)
                    │
                    └──► Docker Publish (GHCR)
```

## Workflows

### 1. CI (`ci.yml`) — Every push & PR

Runs on every push to `master` and every pull request. All jobs run in parallel.

| Job | What it does | Failure blocks merge? |
|-----|-------------|----------------------|
| `backend` | Ruff lint, pip-audit, pytest with 60% coverage threshold | Yes |
| `migration-check` | Verifies Alembic has a single head (no branching) | Yes |
| `frontend` | ESLint, `next build` (includes TypeScript checking), bundle size warning | Yes |
| `frontend-unit` | Vitest unit tests | Yes |
| `frontend-e2e` | Playwright E2E against production build | Yes |
| `docker-build` | Validates both Dockerfiles build successfully | Yes |
| `ci-pass` | Gate job — fails if any upstream job failed | Required status check |

**Performance features:**
- Pip and node_modules caching via `actions/cache`
- Playwright browser caching
- `concurrency` group cancels in-progress CI on new pushes
- Docker BuildKit layer caching via GitHub Actions cache

### 2. Deploy Backend (`deploy-backend.yml`) — master push to `backend/`

Deploys the FastAPI backend to **Fly.io** when backend files change on master.

| Stage | Details |
|-------|---------|
| Preflight | Full lint + test suite must pass |
| Migration notice | Detects new migration files and logs them |
| Deploy | `flyctl deploy --remote-only --strategy rolling` |
| Health check | Polls `/api/v1/health` after deploy |
| Smoke test | Verifies health + course overview endpoints |

**Rolling deployment** ensures zero downtime — Fly.io starts a new machine, waits for health checks, then stops the old one.

**Required secret:** `FLY_API_TOKEN`

### 3. Deploy Frontend (`deploy-frontend.yml`) — master push to `frontend/`

Deploys the Next.js frontend to **Vercel** when frontend files change on master.

| Stage | Details |
|-------|---------|
| Preflight | `npm ci && lint && build && test` |
| Deploy | `vercel deploy --prebuilt --prod` |
| Smoke test | HTTP 200 check on deployed URL |

**Required secrets:** `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`

### 4. Docker Publish (`docker-publish.yml`) — master push & tags

Builds and pushes container images to **GitHub Container Registry (GHCR)**.

| Image | Tags |
|-------|------|
| `ghcr.io/<owner>/rlhf-api` | `latest`, `master`, `<sha>`, `v1.2.3` |
| `ghcr.io/<owner>/rlhf-web` | `latest`, `master`, `<sha>`, `v1.2.3` |

Semver tags (e.g. `v1.0.0`) are triggered by pushing git tags.

### 5. PR Preview (`pr-preview.yml`) — Pull requests

Provides developer feedback directly on PRs.

| Feature | Details |
|---------|---------|
| Change detection | Only runs relevant jobs based on changed paths |
| Migration notice | Posts a sticky PR comment listing new migrations with a review checklist |
| Backend coverage | Runs tests with coverage, posts summary to PR |
| Frontend preview | Deploys a Vercel preview and posts the URL as a PR comment |

### 6. Dependabot (`dependabot.yml`) — Weekly

Automated dependency updates every Monday:

| Ecosystem | Directory | Grouping |
|-----------|-----------|----------|
| pip | `/backend` | Minor + patch grouped |
| npm | `/frontend` | Minor + patch grouped |
| github-actions | `/` | Individual PRs |

## Required Secrets

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Used by | How to get |
|--------|---------|-----------|
| `FLY_API_TOKEN` | `deploy-backend.yml` | `flyctl tokens create deploy` |
| `VERCEL_TOKEN` | `deploy-frontend.yml`, `pr-preview.yml` | Vercel dashboard → Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel CLI (auto) | `vercel link` creates `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | Vercel CLI (auto) | Same as above |

`GITHUB_TOKEN` is provided automatically and used by Docker publish (GHCR).

## Environments

Create a `production` environment in **Settings → Environments** with:
- Required reviewers (optional, for manual approval gate)
- Deployment branch: `master` only

## Database Migrations

Migrations run automatically on each backend deploy via the Dockerfile CMD:

```
alembic upgrade head → seed_task_packs.py → seed_course_content.py → uvicorn
```

**Safety checks:**
1. CI verifies the Alembic migration chain has a single head (no forks)
2. PR preview flags new migrations with a review checklist
3. Rolling deploy on Fly.io means the old version keeps running until the new one is healthy

**Rollback procedure:**
```bash
# 1. Check current state
fly ssh console -C "alembic current"

# 2. Rollback one migration
fly ssh console -C "alembic downgrade -1"

# 3. Deploy previous version
fly deploy --image ghcr.io/<owner>/rlhf-api:<previous-sha>
```

## Release Process

### Regular releases (continuous deployment)
1. Open PR against `master`
2. CI runs, preview deploys, migration notice posted
3. Review and merge
4. Backend auto-deploys to Fly.io (if backend changed)
5. Frontend auto-deploys to Vercel (if frontend changed)
6. Docker images pushed to GHCR

### Tagged releases
```bash
git tag v1.0.0
git push origin v1.0.0
```
This triggers Docker publish with semver tags (`v1.0.0`, `v1.0`).

## Monitoring Post-Deploy

- **Fly.io dashboard:** Machine status, logs, metrics
- **Vercel dashboard:** Deploy status, edge function logs
- **Health endpoint:** `GET /api/v1/health` returns `{"status": "ok"}`
- **Playwright report:** Uploaded as GitHub Actions artifact on E2E failures
