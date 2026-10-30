![Dashboard](docs/dashboard.png)
![API docs](docs/api-docs.png)
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

I built İlanUyum to practice backend development with FastAPI beyond tutorial-level
examples. I used Claude as a pair-programming assistant while building it, then went through
the code to understand every layer. These are the main things I took away:

- **Layered structure.** I keep the database models (`models.py`) and the API schemas
  (`schemas.py`) separate. The models describe tables; the schemas describe what the API
  accepts and returns, so internal fields such as `hashed_password` never leak into a response.
- **Authentication.** Passwords are hashed with Argon2 and never stored in plain text. After
  login the API returns a signed JWT, and a dependency (`get_current_user`) checks it on every
  protected route. Wrong email and wrong password return the same error on purpose, so an
  attacker cannot find out which emails are registered.
- **Authorization.** Every query on applications is filtered by the current user. If someone
  requests another user's application, the API returns 404 instead of 403, so it does not
  reveal that the record exists.
- **Migrations with Alembic.** Instead of `create_all()` I use versioned migrations, so the
  schema can change over time without losing data. The same migration runs on SQLite
  locally and on PostgreSQL in Docker.
- **Testing.** The test suite uses an in-memory SQLite database and FastAPI's dependency
  overrides, so each test starts with a clean database and never touches real data. I tested
  the failure cases too: duplicate emails, invalid input, missing tokens, and access to
  another user's data.
- **PUT vs PATCH.** PUT replaces the whole resource, while PATCH updates only the fields
  that were sent (`model_dump(exclude_unset=True)`).
- **Tooling.** Docker Compose runs the API with PostgreSQL, and GitHub Actions runs ruff and
  pytest on every push. Setting up WSL and virtualization for Docker Desktop on Windows was
  its own lesson in debugging environments.

### What I would improve next

- Add search and sorting for applications.
- Let users upload a CV and compare it with a job posting (the original idea behind the
  project), using background jobs and vector search with pgvector.
- Add refresh tokens and rate limiting for login attempts.