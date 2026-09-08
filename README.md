# Monday Night Raw

Private **7-a-side football statistics and awards** platform for a group of classmates who play every Monday. Turnout is dynamic — some weeks it's 12 people, some weeks it's 20+ across 3 informal teams — so the app tracks who played and who scored/assisted, not fixed teams or a match score.

> Phase 1 (Foundation) is implemented: Django project, database config, models, migrations, seed data.
> Frontend React PWA arrives in Phase 3.

## Architecture

| Layer | Technology |
| --- | --- |
| Backend | Django 6 + Django REST Framework |
| Database | SQLite (WAL mode) — no separate DB server/container |
| Auth | DRF Token Authentication + role-based access (`ADMIN` / `PLAYER`) |
| API docs | OpenAPI via drf-spectacular (`/api/docs/`) |
| Frontend | React + Vite + PWA (Phase 3) |
| Containers | Docker Compose (backend, frontend) |

### Apps

- `accounts` — custom `User` with roles
- `players` — persistent player profiles
- `matches` — matchdays, participants, goal events
- `stats` — performance scoring + statistics services (Phase 2)
- `awards` — weekly / monthly awards

> **Decision:** the Django app is named `stats` instead of `statistics` because `statistics` conflicts with Python’s standard library.

## Features (spec)

- Weekly Monday matchday management — no fixed squad size, teams formed on the pitch
- Post-match goals/assists entry (no score, no team assignment)
- Auto stats, Player of the Week (ties supported), Team of the Week (fixed at 7)
- Monthly awards (auto-generated on finalize) + leaderboards + player profiles
- Admin finalize workflow

## Requirements

- Python 3.12+ (tested with 3.13)
- Node.js 20+ (Phase 3+)

No database server to install — SQLite ships with Python.

## Quick start

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Or via Docker (frontend runs as a live Vite dev server for hot reload):

```bash
cp .env.example .env
docker compose up --build
```

## Seed credentials

| Role | Username | Password |
| --- | --- | --- |
| Admin | `admin` | `admin123` |
| Sample player | `alex` (`alex@demo.local`) | `player123` |

Real players self-register from the login page — `seed_data` only bootstraps
the admin and this one sample player.

## Environment variables

See `.env.example` for the full list. Important keys:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `SQLITE_DB_PATH` — overrides where the SQLite file lives (defaults to `backend/db.sqlite3`)
- `CORS_ALLOWED_ORIGINS`
- `SEED_ADMIN_*`
- Performance weights: `GOAL_WEIGHT`, `ASSIST_WEIGHT` (goals + assists only — no team/score to derive anything else from)

## API documentation

After the server is running:

- Schema: [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)
- Swagger UI: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)

REST endpoints for players/matches/awards land in **Phase 2**.

## API endpoints (Phase 2)

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/auth/register/` | Self-registration; creates User + Player, returns token + user |
| POST | `/api/auth/login/` | Returns token + user |
| POST | `/api/auth/logout/` | |
| GET | `/api/auth/me/` | |
| GET/POST | `/api/players/` | Admin write |
| GET | `/api/players/{id}/statistics/` | |
| GET | `/api/players/{id}/match-history/` | |
| GET/POST | `/api/matches/` | Admin write |
| POST | `/api/matches/{id}/participants/` | Who played — no team split, no squad-size fixed cap |
| POST | `/api/matches/{id}/goals/` | `{goals: [{scorer_id, assister_id?}], also_played?: [id...]}` — no score, no team |
| POST | `/api/matches/{id}/finalize/` | Auto-selects Player of the Week, Team of the Week, and that month's awards |
| POST | `/api/matches/{id}/reopen/` | Admin correction |
| GET | `/api/leaderboard/?ordering=-goals` | |
| GET | `/api/dashboard/` | |
| GET | `/api/awards/weekly/` | |
| GET/POST | `/api/awards/monthly/` | POST generates month |
| GET | `/api/docs/` | Swagger UI |

## Tests

```bash
cd backend
python manage.py test matches.tests.test_match_flow awards.tests.test_awards
```

## Development process

1. **Phase 1 — Foundation** ✅ models, migrations, seed, Docker
2. **Phase 2 — Backend** ✅ REST API, services, validation, tests
3. **Phase 3 — Frontend** ✅ React PWA (admin + player workflows)
4. **Phase 4 — Integration** ✅ login → goals/assists (+ also played) → finalize → stats/awards
5. **Phase 5 — Polish** ✅ spec audit fixes (manual teams, ALLOWED_HOSTS, docs)

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` to Django on port 8000.

Build PWA:

```bash
cd frontend
npm run build
npm run preview
```

## Deployment notes

1. Set strong `SECRET_KEY`, `DEBUG=False`, and production `ALLOWED_HOSTS` / `CORS_ALLOWED_ORIGINS`.
2. Run `python manage.py migrate && python manage.py collectstatic`.
3. Serve the Django API behind gunicorn (single worker — see below) + reverse proxy.
4. Build the frontend (`npm run build`) and serve `frontend/dist` via nginx (or a CDN), pointing `VITE_API_BASE_URL` at the API origin at build time.
5. Configure HTTPS and secure cookies/tokens in production.
6. Back up the SQLite file (`SQLITE_DB_PATH`, or its Docker volume) regularly — it's the entire database.

### Production deployment with Docker (`docker-compose.prod.yml`)

Sized for a small single-box deploy (e.g. a 1GB-RAM VM) — no Node process and
no separate database container at runtime.

```bash
cp .env.example .env
# then edit .env: SECRET_KEY, ALLOWED_HOSTS (your host/IP), CORS_ALLOWED_ORIGINS,
# SEED_ADMIN_USERNAME/SEED_ADMIN_PASSWORD — do NOT reuse the dev defaults.

docker compose -f docker-compose.prod.yml up --build -d
```

Differences from the dev `docker-compose.yml`:

- **Frontend** (`frontend/Dockerfile.prod`) is a multi-stage build: Vite compiles
  the static PWA bundle, then a plain `nginx:alpine` (~75MB image) serves it —
  no Node/Vite dev server running in production. Nginx also serves
  `/static/` and `/media/` directly from shared volumes and reverse-proxies
  `/api/` and `/admin/` to the backend, so only port 80 needs to be public.
- **Backend** runs `gunicorn` with a **single worker process** (`--workers 1
  --threads 4`) instead of `runserver`. SQLite allows only one writer at a
  time, so one process avoids cross-process lock contention on the db file;
  WAL mode still lets reads proceed concurrently with a write. It still runs
  `seed_data` to create the admin account and one sample player — from
  `SEED_ADMIN_USERNAME`/`SEED_ADMIN_PASSWORD` in `.env`, which **must** be
  changed from the dev defaults before deploying. The sample player's
  password (`player123`) is not env-configurable, so delete or deactivate
  that account once real players start self-registering.
- The SQLite file lives on a named volume (`sqlite_data`, mounted at
  `/app/data`) so it survives container recreation — there's no separate
  database container at all.
- Each service has a `mem_limit` (backend 350MB, frontend 64MB — under 420MB
  total, leaving most of a 1GB box free) so one container can't starve the
  other; tune these to match what you actually observe under load.
- Uses an explicit Compose project name (`mnraw-prod`) so its volumes never
  collide with the dev `docker-compose.yml`'s if both are ever run on the
  same host.

Only the frontend/nginx container's port 80 is published to the host — the
backend has no exposed port, so all traffic goes through one reverse-proxied
entry point.

## Design decisions

1. **No teams, no score.** Turnout is dynamic (12 one week, 20+ across 3 informal teams the
   next), so teams are formed on the pitch and never tracked in the app — a matchday just
   records who played (`MatchParticipant`) and who scored/assisted (`GoalEvent`).
2. **GoalEvent** is the source of truth for goals and assists.
3. **No clean sheets, wins, or losses** — those need a team side and a score, neither of which
   exists. Performance score is goals + assists only (`stats/scoring.py`).
4. **Player of the Week / Team of the Week / monthly awards** are computed automatically from
   match performance on finalize and stored as `Award` + `AwardRecipient` rows — there is no
   separate "Player of the Match" concept, since with one match per week the two would always
   be the same player.
5. **Team of the Week is fixed at 7** regardless of turnout — it ranks that day's attendees by
   goals+assists and takes the top 7 (or all of them, if fewer than 7 played), so a
   big-turnout day doesn't inflate it into a 10+ person "team".
6. **No squad-size limit at all.** Participants are derived from whoever scores/assists that
   day (`replace_goals`), and finalize accepts any count — the only requirement is at least
   one participant.
7. **Performance weights** live in `settings.PERFORMANCE_SCORE_WEIGHTS` / `stats/scoring.py`.
8. **SQLite (WAL mode)** is the only database — no separate DB server/container, sized for a small single-box deploy. Production runs a single gunicorn worker process to avoid cross-process write-lock contention on the db file.
