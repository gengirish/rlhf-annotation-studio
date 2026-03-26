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
│   ├── src/app/                      ← Auth, dashboard, task routes
│   └── tests/e2e/                    ← Playwright E2E tests
├── backend/                          ← FastAPI + Neon PostgreSQL (optional)
│   ├── app/                          ← API routers, models, services
│   ├── src/rlhf_api/                 ← src-layout package entrypoint
│   └── README.md
├── docker/
│   └── docker-compose.yml            ← Full-stack local orchestration
├── tasks/
│   ├── code-review-comparisons.json  ← Code review annotation tasks
│   └── safety-alignment.json         ← Safety & alignment evaluation tasks
├── guidelines/
│   ├── comparison-rubric.md          ← How to annotate comparison tasks
│   ├── rating-rubric.md              ← How to annotate rating tasks
│   ├── ranking-rubric.md             ← How to annotate ranking tasks
│   └── safety-guidelines.md          ← Safety & bias evaluation criteria
├── templates/
│   ├── task-template.md              ← JSON schema for creating new tasks
│   └── annotation-export-example.md  ← Example of what exported annotations look like
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

## API Endpoints and Auth Expectations

When `API_BASE` is configured, the UI uses these endpoints:

| Method | Path | Used by UI | Auth required |
|-----|-----|-----|-----|
| `POST` | `/api/v1/auth/register` | Yes (new user flow) | No |
| `POST` | `/api/v1/auth/login` | Yes (returning user flow) | No |
| `GET` | `/api/v1/health` | Optional diagnostics | No |
| `GET` | `/api/v1/inference/status` | Yes (capability check) | No |
| `GET` | `/api/v1/inference/models` | Yes (model picker) | No |
| `POST` | `/api/v1/inference/stream` | Yes (live streaming text) | Optional (`INFERENCE_REQUIRE_AUTH=true`) |
| `POST` | `/api/v1/inference/complete` | Optional/non-stream use | Optional (`INFERENCE_REQUIRE_AUTH=true`) |
| `GET` | `/api/v1/sessions/{session_id}/workspace` | Yes (restore workspace) | No (session ID based) |
| `PUT` | `/api/v1/sessions/{session_id}/workspace` | Yes (autosync) | No (session ID based) |
| `GET` | `/api/v1/tasks/packs` | Yes (task library catalog) | No |
| `GET` | `/api/v1/tasks/packs/{slug}` | Yes (load full task pack) | No |
| `POST` | `/api/v1/tasks/validate` | Yes (validate loaded tasks) | No |
| `POST` | `/api/v1/sessions/bootstrap` | Legacy/optional path | No |

Notes:
- Current UI auth flow uses `/auth/register` and `/auth/login` and stores JWT in localStorage.
- Session workspace routes currently rely on possession of `session_id` (not JWT enforcement).
- Inference routes enforce JWT only when `INFERENCE_REQUIRE_AUTH=true`.

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
