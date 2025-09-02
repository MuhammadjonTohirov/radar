# Repository Guidelines

## Project Structure & Module Organization
- Root: Docker orchestration (`docker-compose.yml`), infra (`infra/docker`), examples (`.env.example`).
- `server/`: Django app and runtime.
  - `radar_project/`: project settings and URLs.
  - Apps: `radars/` (domain models/views), `api/` (DRF serializers/views/urls), `frontend/` (templates/static/forms).
  - Assets: templates in `server/frontend/templates/…`, static in `server/frontend/static/…`.
  - DB: local SQLite at `server/db.sqlite3` by default; PostGIS via Docker.

## Build, Test, and Development Commands
- Local Python setup:
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -r server/requirements.txt`
  - `python server/manage.py migrate`
  - `python server/manage.py runserver`
- Docker (Postgres + web + redis):
  - `docker-compose up --build`
  - Overrides: set `DATABASE_URL` and other envs via `.env` or compose.
- Tests:
  - `python server/manage.py test` (runs Django tests across apps).

## Coding Style & Naming Conventions
- Python: 4‑space indentation; follow PEP 8.
- Django:
  - Models/Classes: `PascalCase` (e.g., `RadarItem`).
  - Functions/vars/files: `snake_case` (e.g., `create_radar`).
  - URLs named with clear verbs (e.g., `radar-list`, `radar-detail`).
- Project layout: put domain logic in `radars/`, API transformation in `api/serializers.py`, view logic in corresponding app.
- Keep settings/environment access centralized in `radar_project/settings.py` via `decouple.config`.

## Testing Guidelines
- Framework: Django `TestCase` in `server/*/tests.py`.
- Place tests near the app being changed (e.g., `server/radars/tests.py`).
- Name tests with behavior focus: `test_creates_radar_on_valid_payload`.
- Prefer small, isolated tests; add API tests when changing serializers/views.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject (≤72 chars), optional body for context.
  - Example: `Fix radar form client‑side validation`.
- PRs must include:
  - Clear description of change and rationale.
  - Linked issue (if any) and migration notes.
  - Screenshots/GIFs for frontend changes (`server/frontend/...`).
  - How to test locally (commands and steps).

## Security & Configuration Tips
- Never commit secrets. Copy `.env.example` to `.env` (root or `server/.env`) and fill values (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`).
- Local default DB is SQLite; Docker uses PostGIS via `DATABASE_URL` in compose.
- Review CORS and DEBUG in `radar_project/settings.py` before deploying.

