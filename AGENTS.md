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
