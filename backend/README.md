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
   http://127.0.0.1:3000/auth
   ```

3. Register once — the app creates a **work session** in Neon and syncs workspace JSON on each save.

## API (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness |
| POST | `/api/v1/sessions/bootstrap` | Body `{ "annotator": { "name", "email", "phone" } }` → `{ annotator, session_id }` |
| GET | `/api/v1/sessions/{session_id}/workspace` | Load tasks, annotations, timings |
| PUT | `/api/v1/sessions/{session_id}/workspace` | Body `{ tasks, annotations, task_times, active_pack_file }` |
| GET | `/api/v1/tasks/packs` | List all task packs (slug, name, description, language, task_count) |
| GET | `/api/v1/tasks/packs/{slug}` | Full task pack with tasks_json array |
| POST | `/api/v1/tasks/validate` | Validate an array of task items |
| GET | `/api/v1/inference/status` | Whether inference is enabled and a Hugging Face token is configured (no secrets returned) |
| POST | `/api/v1/inference/complete` | Live completions: body `{ prompt, system?, slots: [{ label?, hf_model?, temperature?, seed? }] }` → `{ slots: [{ label, text, model, error }] }` |

### Hugging Face live responses

1. Create a [fine-grained token](https://huggingface.co/settings/tokens) with **Make calls to Inference Providers**.
2. In `.env`: `HF_API_TOKEN=hf_...` (or `HF_TOKEN`).
3. Optional: `HF_DEFAULT_MODEL`, `HF_ROUTER_BASE_URL` (default `https://router.huggingface.co/v1`).
4. In the UI, sign in and use the dashboard task flow. The frontend calls `/api/v1/inference/*` directly via `NEXT_PUBLIC_API_URL`.
5. Set `INFERENCE_REQUIRE_AUTH=true` if the API is public and you want to require a JWT from `/api/v1/auth/login`.

## Environment

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Optional sync URL for Alembic (`postgresql+psycopg://...`). If omitted, `+asyncpg` is swapped to `+psycopg`. |
| `CORS_ORIGINS` | Comma-separated origins allowed for the browser UI |
| `ROOT_PATH` | Optional reverse-proxy subpath |
| `DEBUG` | `true` to echo SQL |
| `HF_API_TOKEN` / `HF_TOKEN` | Hugging Face token for Inference Providers router |
| `HF_DEFAULT_MODEL` | Default Hub model id for `/inference/complete` |
| `INFERENCE_REQUIRE_AUTH` | `true` to require `Authorization: Bearer` (JWT) on inference routes |
| `INFERENCE_MAX_TOKENS` | Max new tokens per completion (default `1024`) |
| `INFERENCE_TIMEOUT_SECONDS` | HTTP timeout to HF router (default `120`) |
