# RLHF Annotation Studio

A lightweight annotation platform for practicing Reinforcement Learning from Human Feedback (RLHF) workflows. The project now uses a **Pure Next.js frontend** with a **FastAPI backend**, preserving the original annotation workflows with a production-friendly architecture.

**Frontend:** Next.js App Router app in `frontend/`.

**Backend:** FastAPI in `backend/` (with `src/rlhf_api` package compatibility wrapper), workspace sync to PostgreSQL/Neon, and live Hugging Face inference routes. See `backend/README.md`.

**Local full stack:** `docker/docker-compose.yml` provides `frontend`, `backend`, `postgres`, and `redis` services.

## Quick Start

1. Start backend API (`backend/`) and frontend (`frontend/`)
2. Open `http://localhost:3000/auth`
3. Sign in / register, load a task pack from dashboard, and annotate tasks
4. Use in-app export actions (Markdown / JSONL)

---

## Operating Modes

Choose the mode that matches your class/lab setup:

### 1) Local + API (development/full-stack)
- Run FastAPI from `backend/` and Next.js from `frontend/`.
- Open `http://127.0.0.1:3000/auth`.
- Uses `/api/v1/auth/register` and `/api/v1/auth/login` for JWT + `session_id`.
- Workspace autosaves through `/api/v1/sessions/{session_id}/workspace`.

See `backend/README.md` for setup and env vars.

### 2) Vercel + Fly production
- Deploy Next.js frontend from `frontend/` and API to Fly (`backend/fly.toml`).
- In Vercel, set project **Root Directory** to `frontend/` (recommended monorepo setup).
- Configure backend env (`DATABASE_URL`, `CORS_ORIGINS`, `JWT_SECRET`, optional HF settings).
- Enable `INFERENCE_REQUIRE_AUTH=true` when the API is public.

See `deploy/DEPLOY-VERCEL-FLY.md` for the exact CLI workflow.

#### Live Deployment URLs

| Service | URL |
|---------|-----|
| Frontend | https://rlhf-annotation-frontend.vercel.app |
| Auth | https://rlhf-annotation-frontend.vercel.app/auth |
| Dashboard | https://rlhf-annotation-frontend.vercel.app/dashboard |
| API (direct) | https://rlhf-annotation-api.fly.dev |
| API health | https://rlhf-annotation-frontend.vercel.app/api/v1/health |
| Task packs | https://rlhf-annotation-frontend.vercel.app/api/v1/tasks/packs |
| API docs | https://rlhf-annotation-api.fly.dev/api/docs |

---

## What's Included

```
RLHF/
├── frontend/                         ← Next.js App Router frontend
│   ├── src/app/
│   │   ├── auth/                     ← Login / register
│   │   ├── dashboard/                ← Task library, stats, session sync
│   │   ├── task/[taskId]/            ← Annotation workflow
│   │   ├── reviews/                  ← Review queue + pending + team
│   │   ├── team/                     ← Team management (admin/reviewer)
│   │   ├── analytics/                ← Session metrics
│   │   ├── settings/                 ← Org settings
│   │   └── author/                   ← Task authoring
│   ├── src/lib/                      ← API client, Zustand store
│   └── tests/e2e/                    ← Playwright E2E tests
├── backend/                          ← FastAPI + Neon PostgreSQL
│   ├── app/
│   │   ├── auth.py                   ← JWT auth + role-based dependencies
│   │   ├── routers/                  ← health, auth, sessions, tasks, reviews, orgs, inference, metrics
│   │   ├── models/                   ← Annotator (with role), Organization, ReviewAssignment, etc.
│   │   └── schemas/                  ← Pydantic request/response models
│   ├── alembic/versions/             ← DB migrations (001–007)
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
- **Offline-first local persistence** — works fully client-side without any backend
- **Optional API sync** — persist workspace snapshots to backend/Neon when `API_BASE` is set
- **Optional authenticated inference** — Hugging Face-backed live generation via FastAPI endpoints

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

When `API_BASE` is configured, the UI uses these endpoints:

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/register` | No | Create account → JWT + session_id |
| `POST` | `/api/v1/auth/login` | No | Login → JWT + session_id (response includes `role` and `org_id`) |

### Health & Inference
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/health` | No | Liveness check |
| `GET` | `/api/v1/inference/status` | No | Whether inference is enabled |
| `GET` | `/api/v1/inference/models` | No | Available HF model list |
| `POST` | `/api/v1/inference/stream` | Optional | Live streaming text generation |
| `POST` | `/api/v1/inference/complete` | Optional | Multi-slot parallel completions |

### Sessions & Workspace
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/sessions/bootstrap` | No | Legacy bootstrap path |
| `GET` | `/api/v1/sessions/{id}/workspace` | JWT | Load workspace snapshot |
| `PUT` | `/api/v1/sessions/{id}/workspace` | JWT | Save workspace snapshot |
| `GET` | `/api/v1/sessions/{id}/workspace/history` | JWT | Last 20 workspace revisions |

### Tasks
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/tasks/packs` | No | List task pack catalog |
| `GET` | `/api/v1/tasks/packs/{slug}` | No | Full task pack with tasks |
| `POST` | `/api/v1/tasks/packs` | JWT | Create task pack |
| `PUT` | `/api/v1/tasks/packs/{slug}` | JWT | Update task pack |
| `DELETE` | `/api/v1/tasks/packs/{slug}` | JWT | Delete task pack |
| `POST` | `/api/v1/tasks/validate` | No | Validate task array |
| `POST` | `/api/v1/tasks/score-session` | JWT | Score session against gold tasks |

### Reviews (role-gated)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/reviews/queue` | JWT | Current user's assigned tasks |
| `GET` | `/api/v1/reviews/pending` | JWT (admin/reviewer) | All submitted reviews awaiting approval |
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
| `GET` | `/api/v1/orgs/{id}/team-stats` | JWT (admin/reviewer) | Per-member annotation stats |

### Metrics
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/metrics/session/{id}/summary` | JWT | Session completion stats |
| `GET` | `/api/v1/metrics/session/{id}/timeline` | JWT | Completion timeline |

Notes:
- Auth uses JWT stored in localStorage. Login/register return token, annotator (with role), and session_id.
- Inference routes enforce JWT only when `INFERENCE_REQUIRE_AUTH=true`.
- Review and org management endpoints enforce role-based access (admin or reviewer required).

---

## Troubleshooting Matrix

| Symptom | Likely cause | What to check | Fix |
|--------|--------------|---------------|-----|
| Browser shows CORS error on `/api/v1/*` | Frontend origin not allowed | Backend `CORS_ORIGINS`; exact page URL origin | Add exact origin(s), redeploy API |
| `401` on `/api/v1/inference/stream` or `/complete` | Inference auth enabled but token missing/invalid | `INFERENCE_REQUIRE_AUTH`; `Authorization: Bearer ...` header; token age | Log in again, ensure token is sent, verify `JWT_SECRET` consistency |
| Inference status says unavailable/configured false | Missing/invalid HF token or inference disabled | `HF_API_TOKEN`/`HF_TOKEN`; `INFERENCE_ENABLED`; API logs | Set valid HF token, enable inference, restart API |
| Register/login fails (`401`/`409`) | Bad credentials or existing email | `/api/v1/auth/login` and `/auth/register` responses | Use correct password; for `409`, log in instead of registering |
| Sync silently stops or workspace not restored | Bad `API_BASE`, missing `session_id`, network/API failure | Browser Network tab for `/sessions/{id}/workspace`; localStorage keys | Re-login to refresh token/session, verify `?api=` URL, confirm API health |
| Vercel app cannot reach API (`404`/`502`) | Missing rewrite or Fly app down | `vercel.json` rewrite target; `fly status`; `/api/v1/health` on Fly | Re-run rewrite sync script, redeploy Vercel/Fly, verify Fly hostname |

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
3. Students open the app at `/auth`, load the task file, and annotate
4. Students export their annotations as Markdown and submit
5. Review submissions — the structured Markdown format makes comparison easy

### Assessment Ideas

- Compare student annotations to a "gold standard" annotation set
- Measure inter-annotator agreement across the class
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

The project has three test layers. All commands below assume you are in the repo root.

### Backend unit tests (pytest)

```bash
cd backend
pip install -e ".[dev]"
python -m pytest -q
```

Covers auth, workspace, orgs, reviews, tasks, metrics, annotation validation, and gold scoring (82 tests).

### Frontend unit tests (Vitest)

```bash
cd frontend
npm run test          # single run
npm run test:watch    # watch mode
```

Covers Zustand store actions and the API client (26 tests).

### Frontend E2E tests (Playwright)

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

Covers auth, dashboard, task annotation, export/validation, responsive layout, reviews, settings, author, and analytics (6 spec files).

### Run everything

```bash
npm run test:all
```

CI runs all three layers on every push to `master` and on pull requests (see `.github/workflows/ci.yml`).

---

## Release Gate

A production release is blocked unless **all three** checks are complete:

- [ ] **All tests pass**  
      Run backend test suite from `backend/` (example: `python -m pytest`).
- [ ] **Deploy smoke pass**  
      Run `scripts/e2e-test.ps1` and confirm `0 failed` in the summary.
- [ ] **Manual scenario checklist completed**  
      Validate critical user flows:
  - create account and log in;
  - load a task pack and submit at least one task;
  - verify workspace autosync indicator shows state transitions (idle -> syncing -> synced);
  - export Markdown/JSONL successfully.
