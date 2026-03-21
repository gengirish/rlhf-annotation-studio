# RLHF Annotation API

FastAPI + **async SQLAlchemy** + **Neon PostgreSQL** backend for [RLHF Annotation Studio](../annotation-tool.html).

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

## Connect the HTML UI

1. Serve the repo root over HTTP (so `tasks/*.json` loads), e.g.:
   ```bash
   cd ..
   python -m http.server 8080
   ```

2. Open:
   ```
   http://127.0.0.1:8080/annotation-tool.html?api=http://127.0.0.1:8000
   ```

   Or set `<meta name="rlhf-api-base" content="http://127.0.0.1:8000">` in `annotation-tool.html`.

3. Register once — the app creates a **work session** in Neon and syncs workspace JSON on each save.

## API (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness |
| POST | `/api/v1/sessions/bootstrap` | Body `{ "annotator": { "name", "email", "phone" } }` → `{ annotator, session_id }` |
| GET | `/api/v1/sessions/{session_id}/workspace` | Load tasks, annotations, timings |
| PUT | `/api/v1/sessions/{session_id}/workspace` | Body `{ tasks, annotations, task_times, active_pack_file }` |

## Environment

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Optional sync URL for Alembic (`postgresql+psycopg://...`). If omitted, `+asyncpg` is swapped to `+psycopg`. |
| `CORS_ORIGINS` | Comma-separated origins allowed for the browser UI |
| `ROOT_PATH` | Optional reverse-proxy subpath |
| `DEBUG` | `true` to echo SQL |
