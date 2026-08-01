# RLHF Annotation Studio

A lightweight annotation platform for practicing Reinforcement Learning from Human Feedback (RLHF) workflows. The project uses a **Pure Next.js frontend** with a **FastAPI backend**, preserving the original annotation workflows with a production-friendly architecture.

**Frontend:** Next.js App Router app in `frontend/`.

**Backend:** FastAPI in `backend/` (with `src/rlhf_api` package compatibility wrapper), workspace sync to PostgreSQL/Neon, live Hugging Face inference routes, and extended APIs for quality, exams, datasets, webhooks, and more. See `backend/README.md`.

**Local full stack:** `docker/docker-compose.yml` provides `frontend`, `backend`, `postgres`, and `redis` services.

## Quick Start

1. Start backend API (`backend/`) and frontend (`frontend/`)
2. Open `http://localhost:3000/sign-in`
3. Sign in / register, load a task pack from dashboard, and annotate tasks
4. Use in-app export actions (Markdown / JSONL)

---

## Operating Modes

Choose the mode that matches your class/lab setup:

### 1) Local + API (development/full-stack)
- Run FastAPI from `backend/` and Next.js from `frontend/`.
- Open `http://127.0.0.1:3000/sign-in`.
- Uses `/api/v1/auth/register` and `/api/v1/auth/login` for JWT + `session_id`.
- Workspace autosaves through `/api/v1/sessions/{session_id}/workspace`.

See `backend/README.md` for setup and env vars.

### 2) Vercel + Fly production
- Deploy Next.js frontend from `frontend/` and API to Fly (`backend/fly.toml`).
- In Vercel, set project **Root Directory** to `frontend/` (recommended monorepo setup).
- Configure backend env (`DATABASE_URL`, `CORS_ORIGINS`, `JWT_SECRET`, optional HF settings).
- Enable `INFERENCE_REQUIRE_AUTH=true` when the API is public.

See `deploy/DEPLOY-VERCEL-FLY.md` for the exact CLI workflow.

#### Production hardening

Set `APP_ENV=production` on the API (already set in `backend/fly.toml`). This turns two
silent misconfigurations into startup failures rather than live security holes:

| Guard | Behaviour with `APP_ENV=production` |
|-------|--------------------------------------|
| `JWT_SECRET` still at its default | Startup aborts — the default is public, so tokens would be forgeable |
| `CORS_ORIGINS` empty or `*` | Startup aborts — any site could otherwise drive the API as a logged-in user |

Other production behaviour:

- **Rate limiting** is per-client and in-process: 30 requests/60s on `/api/v1/inference/*`,
  and 10 attempts/300s on `/api/v1/auth/login` and `/register`. Clients are identified from
  `Fly-Client-IP` / `X-Forwarded-For`, so uvicorn must run with `--proxy-headers`
  (set in `backend/Dockerfile`). **State is per-process** — move to a shared store such as
  Redis before running more than one machine.
- **Security headers** (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`,
  `Permissions-Policy`) are set in `frontend/next.config.mjs`, so they apply to both the
  Vercel deployment and the standalone Docker build.
- **`robots.ts`** keeps authenticated routes out of search indexes. Its path list mirrors
  the protected prefixes in `frontend/src/middleware.ts` — update both together.

#### Authentication (Clerk)

Sign-in is handled by [Clerk](https://clerk.com). The API verifies Clerk session
tokens (RS256) against the instance's public JWKS — no secret is needed on the
request path.

| Piece | Where |
|-------|-------|
| Sign-in / sign-up UI | `frontend/src/app/sign-in`, `.../sign-up` (Clerk components) |
| Route protection | `frontend/src/middleware.ts` — **`middleware.ts`, not `proxy.ts`**; the rename only landed in Next 16 and this app is on 15.x, where a `proxy.ts` is silently ignored |
| Token verification | `backend/app/services/clerk_auth.py` |
| Identity mapping | `annotators.clerk_user_id` (migration `022`) |

**Roles stay in the database, not in Clerk.** `require_role` and 125 call sites
read `Annotator.role`; Clerk only proves *who* the user is.

On first Clerk sign-in the API links the session to an existing annotator by
email, so migrated users keep their annotations, role, org and work session. A
genuinely new user is provisioned just-in-time along with a `WorkSession`.

##### Migration window

`LEGACY_JWT_ENABLED=true` makes the API accept **both** Clerk tokens and the old
HS256 tokens, so nobody is signed out mid-session. Turn it off once everyone has
migrated:

```sql
SELECT count(*) FROM annotators WHERE clerk_user_id IS NULL;
```

Import existing users (preserves their bcrypt passwords — no reset emails):

```bash
cd backend
python scripts/import_users_to_clerk.py --dry-run --skip-test-accounts   # preview
python scripts/import_users_to_clerk.py --skip-test-accounts             # run
```

`--skip-test-accounts` omits `e2e-*` / `bench-*` addresses left by the test
suites; Clerk bills per user, so importing those is wasted spend. The script is
idempotent and safe to re-run.

#### End-to-end tests

```bash
cd backend && python scripts/create_e2e_clerk_user.py   # once, creates the Clerk test user
cd frontend && npm run test:e2e
```

Because `clerkMiddleware` enforces auth on the server, the suite cannot fake its
way into protected routes. Playwright runs three projects:

| Project | What it does |
|---------|--------------|
| `setup` | Signs in one real Clerk user, saves the session to `frontend/.auth/` |
| `e2e` | The main suite, reusing that session |
| `signed-out` | `auth-flows.spec.ts`, deliberately with no session |

Roles are still mocked — specs stub `/api/v1/auth/me` via
`tests/e2e/helpers/auth.ts`, so a single Clerk account covers annotator,
reviewer and admin paths.

The test account must use a `+clerk_test@example.com` address and sign in with
the `email_code` strategy: on a default Clerk instance, password is enabled as an
attribute but **not** as a first factor, so password sign-in fails without an
error. `frontend/.env.local` must also contain the Clerk keys, or the dev server
returns 500 on every route.

#### Live Deployment URLs

| Service | URL |
|---------|-----|
| Frontend | https://rlhf-annotation-studio.vercel.app |
| Sign in (Clerk) | https://rlhf-annotation-studio.vercel.app/sign-in |
| Dashboard | https://rlhf-annotation-studio.vercel.app/dashboard |
| API (direct) | https://rlhf-annotation-api.fly.dev |
| API health | https://rlhf-annotation-studio.vercel.app/api/v1/health |
| Task packs | https://rlhf-annotation-studio.vercel.app/api/v1/tasks/packs |
| API docs | https://rlhf-annotation-api.fly.dev/api/docs |

> **`rlhf-studio.intelliforge.tech` is not currently attached** and returns 404.
> DNS already points at Vercel, but the apex `intelliforge.tech` is registered
> under a different Vercel scope than this project's team, so adding the
> subdomain returns `domain_not_owned`. Attach it from the account that owns the
> apex; no DNS change is needed.

---

## What's Included

```
rlhf-annotation-studio/
├── frontend/                         ← Next.js App Router frontend
│   ├── src/app/
│   │   ├── auth/                     ← Login / register
│   │   ├── dashboard/                ← Task library, stats, session sync
│   │   ├── task/[taskId]/            ← Annotation workflow
│   │   ├── reviews/                  ← Review queue + pending + team
│   │   ├── auto-reviews/             ← LLM-assisted review flows
│   │   ├── quality/                  ← Quality scores, leaderboard, drift, calibration
│   │   ├── analytics/                ← Session metrics
│   │   ├── team/                     ← Team management (admin/reviewer)
│   │   ├── settings/                 ← Org settings
│   │   ├── author/                   ← Task authoring
│   │   ├── datasets/                 ← Dataset library, versions, diff, export
│   │   ├── audit/                    ← Audit log viewer
│   │   ├── webhooks/                 ← Webhook configuration and deliveries
│   │   ├── exams/                    ← Exam list and flows
│   │   ├── exams/review/             ← Instructor review of exam attempts
│   │   ├── exams/[examId]/attempt/[attemptId]/  ← Take / resume an exam
│   │   ├── exams/[examId]/result/[attemptId]/   ← Attempt results
│   │   ├── certificates/           ← Issued certificates (org)
│   │   ├── certificate/[id]/        ← Public certificate verification page
│   │   └── course/                  ← Course modules, sessions, progress
│   ├── src/lib/                      ← API client, Zustand store
│   ├── tests/e2e/                    ← Playwright E2E tests
│   └── tests/unit/                 ← Vitest unit tests (store, API client)
├── sdk/                              ← Python client + CLI (`rlhf` command)
│   ├── src/rlhf_studio/
│   ├── tests/
│   └── README.md
├── backend/                          ← FastAPI + Neon PostgreSQL
│   ├── app/
│   │   ├── auth.py                   ← JWT auth + API keys + role-based dependencies
│   │   ├── routers/                  ← health, auth, sessions, tasks, reviews, orgs,
│   │   │                             ← inference, metrics, api_keys, audit, consensus,
│   │   │                             ← datasets, exams, iaa, judge, quality, webhooks,
│   │   │                             ← course, certificates
│   │   ├── models/                   ← Annotator (with role), Organization, datasets, exams, …
│   │   └── schemas/                  ← Pydantic request/response models
│   ├── alembic/versions/             ← DB migrations (001–021)
│   ├── tasks/                        ← JSON task pack source files
│   └── README.md
├── docker/
│   └── docker-compose.yml            ← Full-stack local orchestration
├── guidelines/
│   ├── comparison-rubric.md          ← How to annotate comparison tasks
│   ├── rating-rubric.md              ← How to annotate rating tasks
│   ├── ranking-rubric.md             ← How to annotate ranking tasks
│   └── safety-guidelines.md          ← Safety & bias evaluation criteria
├── templates/
│   ├── task-template.md              ← JSON schema for creating new tasks
│   └── annotation-export-example.md  ← Example of what exported annotations look like
├── deploy/                           ← Deployment guides (Vercel + Fly)
├── exports/                          ← Save your exported annotations here
└── README.md
```

---

## Task Types

The tool supports three annotation task types that mirror real RLHF workflows:

### Comparison (A/B Testing)
- View two AI responses side-by-side
- Select which response is better (or mark as a tie)
- Rate both on multiple quality dimensions
- Most common task type in RLHF pipelines

### Rating (Absolute Scoring)
- Evaluate a single AI response
- Score it on defined quality dimensions (1–5 Likert scale)
- Used for reward model training data

### Ranking (Ordered Preference)
- View three or more responses
- Drag/reorder them from best to worst
- Used for preference-based training (DPO, RLHF)

---

## Creating Your Own Tasks

1. Read `templates/task-template.md` for the JSON schema
2. Create a new `.json` file in the `tasks/` folder
3. Load it from the dashboard **Task Library** in the Next.js app

Minimal example:

```json
[
  {
    "id": "my-task-1",
    "type": "comparison",
    "title": "My First Task",
    "prompt": "What is the capital of France?",
    "responses": [
      { "label": "Response A", "model": "Model 1", "text": "Paris is the capital of France." },
      { "label": "Response B", "model": "Model 2", "text": "The capital is Lyon, a major city in France." }
    ],
    "dimensions": [
      { "name": "Accuracy", "description": "Is the answer correct?", "scale": 5 }
    ]
  }
]
```

---

## Features

- **Side-by-side response comparison** with click-to-select preference
- **Multi-dimensional Likert ratings** (1–5 scale per dimension)
- **Drag-to-rank interface** for ordering multiple responses
- **Task queue sidebar** with progress tracking and session stats
- **Built-in annotation guidelines** toggle per task
- **Session timer** and per-task time tracking
- **Markdown rendering** in prompts and responses (code blocks, bold, italic, headers)
- **Keyboard shortcuts**: arrow keys to navigate, number keys for quick preference selection
- **Export to Markdown** — copy to clipboard or download as `.md` file
- **Validation** — prevents submission without complete ratings and justification
- **Offline-first local persistence** — core annotation UX works client-side; connect the API for sync and org features
- **Optional API sync** — persist workspace snapshots to backend/Neon when `API_BASE` is set
- **Optional authenticated inference** — Hugging Face-backed live generation via FastAPI endpoints
- **Exams** with integrity monitoring and LLM-as-judge auto-grading
- **Certificates** with public verification links
- **Datasets** with versioning, diff, and export
- **Webhooks** for event notifications
- **Audit logging** for compliance
- **Inter-annotator agreement (IAA)** computation
- **Consensus workflows** for disputed annotations
- **Quality scoring** with leaderboard and drift detection
- **Calibration tests** for ongoing annotator alignment
- **Course content** with modules and progress tracking
- **Python SDK** with CLI (`rlhf` command)
- **API key authentication** (Bearer JWT and `X-API-Key` for programmatic access)

---

## Python SDK

The `sdk/` directory provides a Python client and CLI for programmatic access:

```bash
pip install -e sdk/
rlhf --help
```

See `sdk/README.md` for full documentation.

---

## Roles and Team Workflows

Every annotator has a **role** that controls what they can access:

| Role | Capabilities |
|------|-------------|
| `annotator` | Load task packs, annotate tasks, view own review queue, submit annotations |
| `reviewer` | Everything annotators can do, plus: view pending reviews, approve/reject submissions, assign tasks, view team stats, bulk-assign task packs |
| `admin` | Everything reviewers can do, plus: change member roles, update org settings, manage org membership |

### How roles are assigned

- New users default to `annotator`.
- The user who creates an organization is automatically promoted to `admin`.
- Admins can change any org member's role from the **Team Management** page (`/team`) or via the API.

### Team Management (`/team`)

Accessible to `admin` and `reviewer` roles. Features:
- **Members table** — name, email, role, and per-member annotation stats (assigned/submitted/approved/rejected)
- **Role management** — admins can change any member's role via dropdown
- **Bulk assign** — select a task pack and an annotator, assign all tasks in one click
- **Team reviews** — filterable table of all review assignments with approve/reject actions

### Review workflow

```
Admin/Reviewer assigns task pack to annotator
  → Annotator sees tasks in their Review Queue (/reviews)
  → Annotator completes and submits annotation
  → Status changes to "submitted"
  → Reviewer/Admin sees it in Pending Reviews
  → Reviewer approves or rejects (with optional notes)
  → Status becomes "approved" or "rejected"
```

---

## API Endpoints and Auth Expectations

When `API_BASE` is configured, the UI uses these endpoints. Protected routes accept **JWT** (`Authorization: Bearer <token>`) and, where implemented, **`X-API-Key`** for the same operations as the interactive UI.

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/register` | No | Create account → JWT + session_id |
| `POST` | `/api/v1/auth/login` | No | Login → JWT + session_id (response includes `role` and `org_id`) |

### API Keys (CRUD)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/api-keys` | JWT | Create API key (secret shown once) |
| `GET` | `/api/v1/api-keys` | JWT | List keys (metadata only) |
| `PATCH` | `/api/v1/api-keys/{key_id}` | JWT | Update key (e.g. label) |
| `DELETE` | `/api/v1/api-keys/{key_id}` | JWT | Revoke key |

### Health & Inference
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/health` | No | Liveness check |
| `GET` | `/api/v1/health/ready` | No | Readiness check |
| `GET` | `/api/v1/inference/status` | No | Whether inference is enabled |
| `GET` | `/api/v1/inference/models` | No | Available HF model list |
| `POST` | `/api/v1/inference/stream` | Optional | Live streaming text generation |
| `POST` | `/api/v1/inference/complete` | Optional | Multi-slot parallel completions |

### Sessions & Workspace
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/sessions/bootstrap` | JWT | Legacy bootstrap (deprecated) |
| `GET` | `/api/v1/sessions/{id}/workspace` | JWT | Load workspace snapshot |
| `PUT` | `/api/v1/sessions/{id}/workspace` | JWT | Save workspace snapshot |
| `GET` | `/api/v1/sessions/{id}/workspace/history` | JWT | Last workspace revisions |

### Tasks
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/tasks/packs` | No | List task pack catalog |
| `GET` | `/api/v1/tasks/packs/{slug}` | No | Full task pack with tasks |
| `GET` | `/api/v1/tasks/search` | JWT | Search task packs |
| `POST` | `/api/v1/tasks/packs` | JWT | Create task pack |
| `PUT` | `/api/v1/tasks/packs/{slug}` | JWT | Update task pack |
| `DELETE` | `/api/v1/tasks/packs/{slug}` | JWT | Delete task pack |
| `POST` | `/api/v1/tasks/validate` | No | Validate task array |
| `POST` | `/api/v1/tasks/score-session` | JWT | Score session against gold tasks |

### Reviews (role-gated)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/reviews/queue` | JWT | Current user's assigned tasks |
| `GET` | `/api/v1/reviews/pending` | JWT (admin/reviewer) | Submitted reviews awaiting approval |
| `GET` | `/api/v1/reviews/team` | JWT (admin/reviewer) | All team review assignments (filterable) |
| `POST` | `/api/v1/reviews/assign` | JWT (admin/reviewer) | Assign a single task to an annotator |
| `POST` | `/api/v1/reviews/bulk-assign` | JWT (admin/reviewer) | Assign entire task pack to an annotator |
| `PUT` | `/api/v1/reviews/{id}` | JWT (admin/reviewer) | Approve/reject a submission |
| `POST` | `/api/v1/reviews/{id}/submit` | JWT | Annotator submits their annotation |

### Organizations
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/orgs` | JWT | Create org (creator becomes admin) |
| `GET` | `/api/v1/orgs/{id}` | JWT (member) | Get org details |
| `PUT` | `/api/v1/orgs/{id}` | JWT (admin) | Update org settings |
| `GET` | `/api/v1/orgs/{id}/members` | JWT (member) | List org members |
| `POST` | `/api/v1/orgs/{id}/members` | JWT (member) | Add member by email |
| `PUT` | `/api/v1/orgs/{id}/members/{mid}/role` | JWT (admin) | Change member role |
| `DELETE` | `/api/v1/orgs/{id}/members/{mid}` | JWT (admin) | Soft-remove member from org |
| `GET` | `/api/v1/orgs/{id}/team-stats` | JWT (admin/reviewer) | Per-member annotation stats |

### Metrics
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/metrics/session/{id}/summary` | JWT | Session completion stats |
| `GET` | `/api/v1/metrics/session/{id}/timeline` | JWT | Completion timeline |

### Audit
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/audit/logs` | JWT | Paginated audit log |
| `GET` | `/api/v1/audit/logs/me` | JWT | Current user's activity |
| `GET` | `/api/v1/audit/logs/resource/{resource_type}/{resource_id}` | JWT | History for a resource |
| `GET` | `/api/v1/audit/stats` | JWT | Aggregate audit statistics |

### Consensus
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/consensus/setup` | JWT | Create consensus configuration |
| `GET` | `/api/v1/consensus/config/{task_pack_id}` | JWT | Read configuration |
| `GET` | `/api/v1/consensus/status/{task_pack_id}` | JWT | Status for a pack |
| `GET` | `/api/v1/consensus/next/{task_pack_id}` | JWT | Next consensus task for annotator |
| `POST` | `/api/v1/consensus/tasks/{consensus_task_id}/submit` | JWT | Submit consensus annotation |
| `GET` | `/api/v1/consensus/tasks/{consensus_task_id}` | JWT | Get consensus task |
| `POST` | `/api/v1/consensus/tasks/{consensus_task_id}/resolve` | JWT | Resolve dispute |
| `GET` | `/api/v1/consensus/disputed/{task_pack_id}` | JWT | List disputed tasks |

### Datasets
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/datasets` | JWT | Create dataset |
| `GET` | `/api/v1/datasets` | JWT | List datasets |
| `POST` | `/api/v1/datasets/import` | JWT | Import dataset |
| `GET` | `/api/v1/datasets/{dataset_id}` | JWT | Dataset detail |
| `POST` | `/api/v1/datasets/{dataset_id}/versions` | JWT | Create version |
| `GET` | `/api/v1/datasets/{dataset_id}/versions/{version}` | JWT | Read version |
| `GET` | `/api/v1/datasets/{dataset_id}/versions/{version}/export` | JWT | Export version |
| `GET` | `/api/v1/datasets/{dataset_id}/diff` | JWT | Diff between versions |
| `DELETE` | `/api/v1/datasets/{dataset_id}` | JWT | Delete dataset |

### Exams
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/exams` | JWT (admin) | Create exam |
| `GET` | `/api/v1/exams` | JWT | List exams |
| `GET` | `/api/v1/exams/review/rubric-criteria` | JWT | Rubric criteria for manual review |
| `GET` | `/api/v1/exams/review/attempts` | JWT (admin/reviewer) | Attempts awaiting review |
| `POST` | `/api/v1/exams/review/attempts/{attempt_id}/release` | JWT (admin/reviewer) | Release graded attempt |
| `POST` | `/api/v1/exams/review/attempts/{attempt_id}/judge` | JWT (admin/reviewer) | LLM judge / auto-grade |
| `POST` | `/api/v1/exams/{exam_id}/attempts/start` | JWT | Start or resume attempt |
| `GET` | `/api/v1/exams/{exam_id}/attempts/{attempt_id}` | JWT | Get in-progress attempt |
| `PUT` | `/api/v1/exams/{exam_id}/attempts/{attempt_id}/answer` | JWT | Save answers |
| `POST` | `/api/v1/exams/{exam_id}/attempts/{attempt_id}/integrity-events` | JWT | Log integrity events |
| `POST` | `/api/v1/exams/{exam_id}/attempts/{attempt_id}/submit` | JWT | Submit attempt |
| `GET` | `/api/v1/exams/{exam_id}/attempts/{attempt_id}/result` | JWT | Graded result |

### IAA
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/iaa/compute` | JWT | Compute IAA for selections |
| `GET` | `/api/v1/iaa/summary/{task_pack_id}` | JWT | Latest IAA summary for a pack |

### Judge (LLM evaluations)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/judge/evaluate` | JWT | Run batch judge evaluation |
| `GET` | `/api/v1/judge/evaluations` | JWT | List evaluations |
| `GET` | `/api/v1/judge/evaluations/{task_pack_id}` | JWT | Evaluations for a pack |
| `GET` | `/api/v1/judge/evaluations/{task_pack_id}/{task_id}` | JWT | Single task evaluation |
| `POST` | `/api/v1/judge/evaluations/{evaluation_id}/override` | JWT | Manual override |
| `POST` | `/api/v1/judge/evaluations/{evaluation_id}/accept` | JWT | Accept judge output |
| `POST` | `/api/v1/judge/evaluations/{evaluation_id}/reject` | JWT | Reject judge output |

### Quality
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/quality/score/{annotator_id}` | JWT | Annotator quality score |
| `GET` | `/api/v1/quality/leaderboard` | JWT | Leaderboard |
| `GET` | `/api/v1/quality/dashboard` | JWT | Org quality dashboard |
| `GET` | `/api/v1/quality/drift/{annotator_id}` | JWT (admin/reviewer) | Drift alerts |
| `POST` | `/api/v1/quality/calibration` | JWT (admin) | Create calibration test |
| `GET` | `/api/v1/quality/calibration` | JWT | List calibration tests |
| `POST` | `/api/v1/quality/calibration/{test_id}/attempt` | JWT | Submit calibration attempt |
| `GET` | `/api/v1/quality/calibration/{test_id}/results` | JWT (admin/reviewer) | Calibration results |
| `POST` | `/api/v1/quality/recompute/{annotator_id}` | JWT (admin) | Recompute scores |

### Webhooks
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/webhooks` | JWT | Create webhook |
| `GET` | `/api/v1/webhooks` | JWT | List webhooks |
| `GET` | `/api/v1/webhooks/{webhook_id}` | JWT | Get webhook |
| `GET` | `/api/v1/webhooks/{webhook_id}/deliveries` | JWT | Delivery history |
| `POST` | `/api/v1/webhooks/{webhook_id}/test` | JWT | Send test delivery |
| `PATCH` | `/api/v1/webhooks/{webhook_id}` | JWT | Update webhook |
| `DELETE` | `/api/v1/webhooks/{webhook_id}` | JWT | Delete webhook |

### Course
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/course/overview` | JWT | Course overview |
| `GET` | `/api/v1/course/modules` | JWT | List modules |
| `GET` | `/api/v1/course/modules/{number}` | JWT | Module detail |
| `GET` | `/api/v1/course/sessions/{number}` | JWT | Session content |
| `GET` | `/api/v1/course/sessions/{number}/rubric` | JWT | Session rubric |
| `GET` | `/api/v1/course/sessions/{number}/questions` | JWT | Session questions |
| `GET` | `/api/v1/course/sessions/{number}/resources` | JWT | Session resources |
| `GET` | `/api/v1/course/progress` | JWT | User progress |

### Certificates
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/certificates` | JWT | Issue certificate |
| `GET` | `/api/v1/certificates` | JWT | List org certificates |
| `GET` | `/api/v1/certificates/mine` | JWT | Current user's certificates |
| `GET` | `/api/v1/certificates/{certificate_id}/public` | No | Public verification payload |

Notes:
- Auth uses JWT stored in localStorage for the browser. Login/register return token, annotator (with role), and session_id.
- Programmatic clients may use **Bearer JWT** or **X-API-Key** where the backend exposes `get_current_user_or_api_key`.
- Inference routes enforce JWT only when `INFERENCE_REQUIRE_AUTH=true`.
- Review, org, exam, and quality endpoints enforce role-based access as implemented in each router.

---

## Troubleshooting Matrix

| Symptom | Likely cause | What to check | Fix |
|--------|--------------|---------------|-----|
| Browser shows CORS error on `/api/v1/*` | Frontend origin not allowed | Backend `CORS_ORIGINS`; exact page URL origin | Add exact origin(s), redeploy API |
| `401` on `/api/v1/inference/stream` or `/complete` | Inference auth enabled but token missing/invalid | `INFERENCE_REQUIRE_AUTH`; `Authorization: Bearer ...` header; token age | Log in again, ensure token is sent, verify `JWT_SECRET` consistency |
| Inference status says unavailable/configured false | Missing/invalid HF token or inference disabled | `HF_API_TOKEN`/`HF_TOKEN`; `INFERENCE_ENABLED`; API logs | Set valid HF token, enable inference, restart API |
| Register/login fails (`401`/`409`) | Bad credentials or existing email | `/api/v1/auth/login` and `/auth/register` responses | Use correct password; for `409`, log in instead of registering |
| Sync silently stops or workspace not restored | Bad `API_BASE`, missing `session_id`, network/API failure | Browser Network tab for `/sessions/{id}/workspace`; localStorage keys | Re-login to refresh token/session, verify `?api=` URL, confirm API health |
| Vercel app cannot reach API (`404`/`502`) | Missing rewrite or Fly app down | `frontend/vercel.json` rewrite target; `fly status`; `/api/v1/health` on Fly | Re-run rewrite sync script, redeploy Vercel/Fly, verify Fly hostname |

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `←` / `p` | Previous task |
| `→` / `n` | Next task |
| `1` | Select Response A (comparison tasks) |
| `2` | Select Response B (comparison tasks) |
| `3` | Select Tie (comparison tasks) |

---

## Reading the Guidelines

Before annotating, read the relevant rubric in the `guidelines/` folder:

- **comparison-rubric.md** — How to evaluate A vs B tasks, rating scale definitions, writing good justifications
- **rating-rubric.md** — How to score individual responses, calibration tips
- **ranking-rubric.md** — How to order multiple responses, handling close calls
- **safety-guidelines.md** — The Three H's framework (Helpful, Harmless, Honest), bias checklist, red flags

---

## For Instructors

### Setting Up a Class Exercise

1. Create task files targeting your learning objectives
2. Distribute this folder to students (zip, git, or LMS upload)
3. Students open the app at `/sign-in`, load the task file, and annotate
4. Students export their annotations as Markdown and submit
5. Review submissions — the structured Markdown format makes comparison easy

### Assessment Ideas

- Compare student annotations to a "gold standard" annotation set
- Measure inter-annotator agreement across the class (see **IAA** API and analytics)
- Use **exams** and **calibration tests** for summative and ongoing checks
- Have students create their own task sets and swap with peers
- Discuss disagreements as a class to build calibration

### Suggested Exercises

| Exercise | Task File | Focus |
|----------|-----------|-------|
| Code Review Quality | `code-review-comparisons.json` | Evaluating technical accuracy and completeness |
| Safety & Alignment | `safety-alignment.json` | Detecting bias, evaluating refusals, harm avoidance |
| Built-in Demo | (click "Try Demo Tasks") | General RLHF annotation practice |

---

## How This Relates to Real RLHF

This annotation kit simulates the human feedback collection phase of the RLHF pipeline:

```
Prompt → LLM generates responses → Humans annotate preferences → Train reward model → RL fine-tuning
                                    ^^^^^^^^^^^^^^^^^^^^^^^^
                                    (this is what you're practicing)
```

In production RLHF systems (like those at OpenAI, Anthropic, and Google), human annotators perform thousands of these comparisons and ratings. The quality of this human feedback directly determines the quality of the resulting model. Practicing annotation helps you understand:

- Why annotation guidelines and calibration matter
- How subtle differences in evaluation criteria change outcomes
- The difficulty of maintaining consistency across many tasks
- How bias in annotation can propagate to model behavior

---

## Browser Support

Works in any modern browser: Chrome, Firefox, Edge, Safari. Run with `frontend` + `backend` services for full functionality.

---

## Testing

The project has layered tests. Commands below assume you are in the repo root.

### Backend unit tests (pytest)

```bash
cd backend
pip install -e ".[dev]"
python -m pytest -q
```

Covers auth, workspace and sessions, organizations, reviews, tasks (including validation and search), metrics, gold scoring, API keys, audit, consensus, datasets, webhooks, quality and calibration, IAA, LLM judge and exam judge services, org/judge HTTP routers, and related unit tests (170 tests).

### Frontend unit tests (Vitest)

```bash
cd frontend
npm install
npm run test          # single run
npm run test:watch    # watch mode
```

Covers the Zustand store (`tests/unit/store.test.ts`) and the API client (`tests/unit/api.test.ts`).

### Frontend E2E tests (Playwright)

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

Spec files under `frontend/tests/e2e/`:

- `auth-dashboard.spec.ts`
- `task-annotation.spec.ts`
- `exams-flow.spec.ts`
- `settings-author.spec.ts`
- `auto-reviews.spec.ts`
- `analytics-nav-sync.spec.ts`
- `export-validation.spec.ts`
- `new-features.spec.ts`
- `responsive.spec.ts`

### Python SDK tests

```bash
cd sdk
pip install -e ".[dev]"
python -m pytest -q
```

### Run everything

```bash
npm run test:all
```

CI runs the configured test layers on every push to `master` and on pull requests (see `.github/workflows/ci.yml`).

---

## Alembic migrations

Schema changes live in `backend/alembic/versions/` as numbered revisions **001–021** (annotators/sessions through certificates and related features). Apply with Alembic from `backend/` per `backend/README.md`.

---

## Release Gate

A production release is blocked unless **all** of the following are complete:

- [ ] **Automated tests pass**  
      Backend: `cd backend` then `python -m pytest`.  
      Frontend unit: `cd frontend` then `npm run test`.  
      SDK: `cd sdk` then `python -m pytest` (if shipping SDK changes).  
      Optional: full monorepo `npm run test:all` when dependencies are installed.
- [ ] **Deploy / E2E smoke pass**  
      Run `scripts/e2e-test.ps1` (or equivalent CI Playwright job) and confirm `0 failed` in the summary.
- [ ] **Manual scenario checklist**  
      - Create account and log in (JWT + session).  
      - Load a task pack, annotate, and submit at least one task through the review flow where applicable.  
      - Confirm workspace autosync indicator transitions (idle → syncing → synced).  
      - Export Markdown/JSONL successfully.  
      - Spot-check org-only features you rely on: **datasets** (version/export), **webhooks** (test delivery), **audit** log visibility, **quality** dashboard, **exams** (attempt → submit → result), **certificates** (issue + public link), **course** progress, **API keys** (create/revoke) if used in integrations.
