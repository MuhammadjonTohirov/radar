# Repository Guidelines

## Project Structure & Module Organization
- Root: Docker orchestration (`docker-compose.yml`), infra (`infra/docker`), examples (`.env.example`).
- `server/`: Django app and runtime.
  - `radar_project/`: project settings and URLs.
  - Apps: `radars/` (domain models/views), `api/` (DRF serializers/views/urls), `frontend/` (templates/static/forms).
  - Assets: templates in `server/frontend/templates/...`, static in `server/frontend/static/...`.
  - DB: local SQLite at `server/db.sqlite3` by default; PostGIS via Docker.

## Build, Test, and Development Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
python server/manage.py migrate
python server/manage.py runserver
```
- Run full stack via Docker: `docker-compose up --build` (uses PostGIS, Redis).
- Tests: `python server/manage.py test` (runs Django tests across apps).

## Coding Style & Naming Conventions
- Python: 4-space indentation; follow PEP 8 and match existing style.
- Django: Models/classes `PascalCase` (e.g., `RadarItem`); functions/vars/files `snake_case` (e.g., `create_radar`).
- URLs: clear verbs, e.g., `radar-list`, `radar-detail`.
- Layout: domain logic in `radars/`; API transformation in `api/serializers.py`; view logic in the owning app.
- Configuration: centralize env access in `radar_project/settings.py` via `decouple.config`.

## Testing Guidelines
- Framework: Django `TestCase` in `server/*/tests.py`.
- Place tests near the app changed (e.g., `server/radars/tests.py`).
- Name by behavior (e.g., `test_creates_radar_on_valid_payload`).
- Run locally: `python server/manage.py test`.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject (≤72 chars). Example: `Fix radar form client-side validation`.
- PRs include: clear description and rationale, linked issue (if any), migration notes, screenshots/GIFs for frontend changes (`server/frontend/...`), and local testing steps.

## Security & Configuration Tips
- Never commit secrets. Copy `.env.example` to `.env` (root or `server/.env`) and set `DJANGO_SECRET_KEY`, `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`.
- Local default DB is SQLite; Docker uses PostGIS via `DATABASE_URL` in compose.
- Review CORS and `DEBUG` in `radar_project/settings.py` before deploying.

