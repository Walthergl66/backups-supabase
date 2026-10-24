<<<<<<< HEAD
# Repository Guidelines

## Project Structure & Module Organization

- `backend/` contains the Python application. `api/routes/` holds FastAPI endpoints, `services/` contains business and provider logic, and `backup/`, `bot/`, `notify/`, and `core/` hold their respective responsibilities.
- `backend/db/schema.sql` defines the SQLite schema. `backend/tests/` contains pytest tests and shared fixtures in `conftest.py`.
- `frontend/src/` contains the React application, organized into `components/`, `features/`, `services/`, and `utils/`. Static assets live in `frontend/public/`.
- Docker configuration is at the repository root and in each component directory. Runtime data belongs in `data/`, not source directories.

## Build, Test, and Development Commands

- `docker compose up -d --build` builds and starts the complete application.
- Frontend development: `cd frontend && npm install && npm run dev`. `npm run build` produces production assets; `npm run preview` serves that build locally.
- Backend development: create and activate a virtual environment in `backend/`, install `requirements.txt`, configure `.env` from `.env.example`, then run `python main.py`.
- Backend tests: from `backend/`, install `requirements-dev.txt` and run `pytest -p no:cacheprovider`. Tests use temporary databases under `/tmp`.
- Regenerate PWA icons with `cd frontend && node scripts/generate-icons.mjs`.

## Coding Style & Naming Conventions

- Follow the surrounding code style: Python uses 4-space indentation and `snake_case`; React components use JSX and `PascalCase`, while functions and utilities use `camelCase`.
- Keep API handlers thin and put reusable application logic in backend services. Keep frontend API access in `frontend/src/services/`.
- No repository-wide formatter or linter is configured. Match nearby formatting and keep changes focused.

## Testing Guidelines

- Add backend regression tests under `backend/tests/`, named `test_*.py`; use the shared fixtures where appropriate.
- Run the full pytest command above after backend changes. For frontend changes, run `npm run build` from `frontend/` to catch compilation errors.

## Commit & Pull Request Guidelines

- Recent history follows `type(scope): short description`, for example `fix(api): ...` and `test(import): ...`. Keep the subject concise and describe the change; Spanish descriptions are common.
- A pull request should explain the user-visible change, note relevant configuration or migration impacts, link related issues, and include screenshots for UI changes. Mention the tests or build commands run.

## Security & Configuration

- Never commit `.env` files, credentials, connection strings, or generated backups. Use `.env.example` for variable names and keep encryption keys and runtime data out of version control.
- Treat PostgreSQL connection strings and Supabase tokens as secrets; preserve the existing encryption and redaction behavior when changing credential flows.
=======
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
>>>>>>> origin/main
