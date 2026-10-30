![Dashboard](docs/dashboard.png)
![CI](https://github.com/yigitcangirgin/ilanuyum/actions/workflows/ci.yml/badge.svg)
# İlanUyum

A job application tracker: a clean REST API (FastAPI) with a small, dependency-free web UI.

## Features

- Register and log in with email and password (argon2 hashing, JWT bearer tokens)
- Full CRUD for job applications, with `PUT` (replace) and `PATCH` (partial update)
- Filter by status, paginate with `skip` / `limit`
- Per-status statistics endpoint
- Strict per-user isolation: you can never see or touch another user's data
- Vanilla JS dashboard (no frameworks, no CDNs), light and dark mode, responsive
- Alembic migrations, Docker Compose with PostgreSQL (pgvector image), GitHub Actions CI

## Tech stack

Python 3.12+, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, PyJWT, pwdlib (argon2), Jinja2,
Alembic, SQLite (default) / PostgreSQL, pytest + httpx, ruff, uv.

## Quick start

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs> for the interactive API docs and
<http://127.0.0.1:8000/> for the web UI.

Configuration comes from environment variables or a `.env` file (see `.env.example`):
`DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
Change `SECRET_KEY` outside development.

## Docker quick start

```bash
docker compose up --build
```

This starts PostgreSQL, applies the migrations, and serves the app on port 8000.

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | no | Health check (runs `SELECT 1`) |
| POST | `/auth/register` | no | Create an account (409 if the email exists) |
| POST | `/auth/login` | no | OAuth2 form login, returns a bearer token |
| GET | `/auth/me` | yes | Current user |
| GET | `/applications` | yes | List; `status`, `skip`, `limit` query params |
| GET | `/applications/stats` | yes | Totals and counts per status |
| POST | `/applications` | yes | Create (201) |
| GET | `/applications/{id}` | yes | Read one (404 if missing or not yours) |
| PUT | `/applications/{id}` | yes | Replace |
| PATCH | `/applications/{id}` | yes | Partial update |
| DELETE | `/applications/{id}` | yes | Delete (204) |

## Project structure

```
app/
  main.py            app wiring, static mount
  config.py          settings (pydantic-settings)
  database.py        engine, session, Base, get_db
  models.py          SQLAlchemy models
  schemas.py         Pydantic schemas
  security.py        password hashing, JWT
  deps.py            auth dependencies
  routers/           health, auth, applications, pages
  templates/         Jinja2 pages
  static/            CSS and JS
alembic/             migrations
tests/               pytest suite
docs/                LEARNING_TR.md (Turkish learning guide)
```

## Tests and lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Design decisions

- **Sync SQLAlchemy first.** Simpler to read, debug and test; FastAPI runs sync endpoints in a
  thread pool. Async can come later if it is actually needed.
- **Ownership checks return 404, not 403.** A 403 would confirm that someone else's record exists.
- **Static route before dynamic route.** `/applications/stats` is declared before
  `/applications/{application_id}`, otherwise "stats" would be parsed as an id.
- **Alembic over `create_all`.** The schema is versioned and reproducible; the app never creates tables.
  Tests use `create_all` on an in-memory database.
- **Passwords are hashed with argon2** (via pwdlib), never stored or logged in plain text.
- **JWT access tokens** carry the user id as `sub` and expire (30 minutes by default).

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## What I learned

- 
- 
- 
