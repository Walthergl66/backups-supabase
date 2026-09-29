# AGENTS.md

Single-process system: `backend/main.py` runs FastAPI + Telegram bot polling + APScheduler in one process/container. Do not split into separate services.

## Layout

- `backend/main.py` — sole entrypoint (DB init → admin bootstrap → plaintext sweep → offsite sync → uvicorn + bot + scheduler).
- `backend/services/` — only persistence layer (`accounts, projects, users, web_users, audit, backup_history, refresh_tokens, supabase_api`). New DB access goes here, not inline SQL in `api/` or `bot/`.
- `backend/api/` — FastAPI JSON-only under `/api/*` (JWT Bearer). `api/app.py:create_app()` is the app factory.
- `backend/bot/handlers/` — Telegram commands per domain (`basics, backup_cmd, status_cmd, register, addbd, misc`), wired in `bot/application.py`.
- `backend/backup/` — `pg_dump -Fc` via subprocess + `pg_restore --list` verify + rotation + offsite S3 copy.
- `backend/core/config.py` — typed `settings()` singleton (cached). Tests must reset `cfg._settings = None` after changing env (see `tests/conftest.py`).
- `backend/db/schema.sql` — SQLite schema (accounts, projects, users, permissions, web_users, backup_history, audit_log, refresh_sessions).
- `frontend/src/` — React+Vite+PWA (`services/` mirrors API domains, `http.js` is the fetch wrapper). Served by nginx; `/api` proxied to `backend:8080`.
- `data/` — SQLite + backups volume (gitignored, survives `compose down`). Never commit.
- `docs/DEPLOY_MODELO_A.md` — deploy/runbook (Oracle VM + Tailscale). Check before changing ports, nginx, or compose.

## Commands

```bash
docker compose up -d --build          # normal path; panel on http://localhost:8080 (loopback only)
docker compose logs -f backend        # API + bot logs
cp backend/.env.example backend/.env  # then fill required keys (below)

cd backend && pip install -r requirements-dev.txt && pytest -p no:cacheprovider
cd frontend && npm install && npm run dev   # :5173, proxies /api -> localhost:8000
node scripts/generate-icons.mjs             # regenerate PWA icons (run from frontend/)
```

- No lint/typecheck/CI config exists. Verify with `pytest -p no:cacheprovider` (backend) and `npm run build` (frontend).
- Frontend has no test runner — only `dev | build | preview` scripts.

## Env & gotchas

- Required in `backend/.env`: `BOT_TOKEN`, `ENCRYPTION_KEY`, `BACKUP_ENCRYPTION_KEY`, `SESSION_SECRET`. `config.py` raises `RuntimeError` if any is missing (`load_dotenv` reads `backend/.env`).
- `ENCRYPTION_KEY` (DB credentials) and `BACKUP_ENCRYPTION_KEY` (`.enc` files) are Fernet keys — never reuse one for the other, never rotate blindly: old rows/files become undecryptable. `SESSION_SECRET` rotation invalidates all JWTs.
- Dev port mismatch: `vite.config.js` proxies `/api` to `localhost:8000` but default `WEB_PORT=8080`. Set `WEB_PORT=8000` in local `backend/.env` for `npm run dev`, or point the proxy at 8080.
- Docker networking: only `frontend` publishes a port (`127.0.0.1:8080`); `backend` is `expose`-only and reached as `http://backend:8080`. Healthcheck hits `/api/health`.
- `pytest -p no:cacheprovider` — the `-p no:cacheprovider` flag is required (keeps the read-only container / repo clean of `.pytest_cache`). Tests use per-test SQLite/backs dirs in `/tmp` via the `db` fixture; they never touch `./data`.
- `pg_dump`/`pg_restore` come from `postgresql-client` in `backend/Dockerfile` — required for any local backup run, not just Docker.
- nginx `proxy_read_timeout 660s` must stay above `BACKUP_TIMEOUT_SECONDS` (default 600s) or long `/api` backup calls get cut. PWA workbox is `NetworkOnly` for `/api/*` — never cache API responses.
