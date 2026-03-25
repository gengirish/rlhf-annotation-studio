# Deploy RLHF Annotation Studio (Docker)

One `docker compose` stack:

- **frontend** — Next.js app on port **8080** (host-mapped).
- **api** — FastAPI + Uvicorn on port 8000 inside the compose network.

## Prerequisites

- Docker + Docker Compose v2
- A Neon **PostgreSQL** database and connection string

## 1. Configure environment

From the **repository root** (parent of `deploy/`):

```bash
cp .env.example .env
```

Edit `.env`:

- **`DATABASE_URL`** — must start with `postgresql+asyncpg://` (the app auto-fixes plain `postgresql://` to `+asyncpg` if you forget).
- Remove `channel_binding=require` from the URL if asyncpg fails to connect.
- **`CORS_ORIGINS`** — include every URL you use in the browser (e.g. `http://YOUR_VPS_IP:8080`). Same-origin traffic through nginx often works without tuning CORS.

## 2. Build and run

```bash
docker compose up --build
```

First API start runs `alembic upgrade head` against Neon.

## 3. Test in the browser

1. Open **http://localhost:8080/** (or `http://SERVER_IP:8080/` on a VPS).
2. Register/login and open dashboard — workspace sync should work if the API is up.
3. Load a task pack from the library; annotate; refresh — data should still be in localStorage; server copy updates on save (debounced).

### Quick API checks (optional)

```bash
# Health (through nginx)
curl -s http://localhost:8080/api/v1/health

# Or call API directly (map port in compose for debugging only)
curl -s http://localhost:8000/api/v1/health
```

To expose the API on the host temporarily, add under `api` in `docker-compose.yml`:

```yaml
    ports:
      - "8000:8000"
```

## 4. Production notes

- Use **HTTPS** (Caddy, Traefik, or cloud LB) in front of nginx; set `CORS_ORIGINS` to your `https://` origin.
- Restrict Neon firewall to your server IPs if Neon supports it.
- Rotate DB credentials if `.env` was ever leaked.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `alembic upgrade` fails on start | Check `DATABASE_URL`, SSL, and Neon project status. |
| Task library empty / fetch errors | Ensure `frontend` container is up and check browser network requests to `/api/v1/*`. |
| No “Synced with server” | Check browser devtools → Network for `/api/v1/sessions/bootstrap`. |
| CORS errors | Add your exact page origin to `CORS_ORIGINS`. |
