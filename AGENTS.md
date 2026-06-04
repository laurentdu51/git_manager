# Git Manager App — Agent Guide

## Overview
Django 6.0 web app that manages multiple Git repos: dashboard, remote management, SSH key relay, monitoring, push logs, and notifications (Slack/email). All user-facing strings are in French.

## Tech Stack
- **Python 3.12 / Django >=6.0,<6.1**
- **DB**: SQLite (default) or PostgreSQL (if `DATABASE_URL` set)
- **Server**: Gunicorn + Whitenoise (static files). No ASGI.
- **Frontend**: Server-rendered Django templates + vanilla JS + plain CSS (dark/light theme via CSS variables). No JS build step.
- **Docker**: `python:3.12-slim` base, compose with SSH + cron.
- **CI**: GitHub Actions (`tests.yml`): syntax check, 75 tests, migration check.

## Project Structure
```
config/          — Django project settings (settings.py, urls.py, wsgi.py)
git_manager/     — Single Django app
├── models.py    — 5 models: SshKey, GitRepo, GitRemote, PushLog, RemoteMonitor
├── views.py     — Dashboard, repos, remotes, push, logs, API, monitoring
├── ssh_views.py — SSH key management views
├── forms.py     — Form classes + validators
├── services.py  — GitService (subprocess calls to git)
├── ssh_service.py — SSH key operations
├── middleware.py — API auth decorator + rate-limiting
├── notifications.py — Slack + email alerts
├── urls.py      — All URL patterns (app_name='git_manager')
├── management/commands/ — check_remotes.py, sync_repos.py
├── templates/git_manager/ — 11 HTML templates
├── static/git_manager/ — css/style.css, js/app.js
└── tests/       — test_forms, test_models, test_services, test_views
docker/          — Dockerfile, entrypoint.sh
```

## Key Commands
```bash
# Run all 75 tests
python manage.py test --verbosity=2

# Run a specific test file
python manage.py test git_manager.tests.test_services --verbosity=2

# Check remote status
python manage.py check_remotes [--verbose] [--alerts-only]

# Sync repos from /repos folder
python manage.py sync_repos [--dry-run]

# Run dev server
python manage.py runserver 0.0.0.0:8000

# Lint (no linter configured, only syntax check in CI):
python -m py_compile manage.py config/ git_manager/

# Verify migrations are in sync
python manage.py makemigrations --check --dry-run

# Run via Docker
docker compose up -d --build

# Enter container
docker compose exec web bash
```

## Code Conventions
- **snake_case** for Python files, functions, vars; **PascalCase** for classes
- **camelCase** for JS functions
- 4-space indentation, ~80-100 char lines
- Single quotes in Python, double quotes in templates/JS
- Type hints used in `services.py` and `ssh_service.py` (not consistent everywhere)
- User-facing strings: **French** (model verbose names, form labels, UI text, error messages)
- Code identifiers, comments, logs: **English**
- App verbose_name: `Gestionnaire Git`

## Models
- **SshKey**: name, key_type (rsa/ed25519), public_key, private_key (encrypted), created_at, updated_at
- **GitRepo**: name, path (unique), is_active, ssh_key (FK to SshKey), created_at, updated_at
- **GitRemote**: repo (FK), name, url, is_active, created_at
- **PushLog**: remote (FK), status (success/pending/failed), commit_hash, commit_message, error_message, user, created_at
- **RemoteMonitor**: remote (FK), status (reachable/unreachable), response_time_ms, last_checked, error_message

## Key Patterns
- **GitService** (`services.py`): wraps all `git` subprocess calls. Constructor takes `repo_path`, `ssh_key_path` (optional). Methods: `fetch()`, `pull()`, `push()`, `status()`, `log()`, `list_branches()`, `get_remote_url()`, `repo_exists()`, `init_repo()`, `add_remote()`, `set_url()`, `rename_branch()`, `diff_file_log()`.
- **SSH relay**: local machine → Git Manager (SSH on port 2222) → GitHub/GitLab. Managed via `ssh_service.py`.
- **API auth**: Bearer token via `@api_auth_required` decorator + `@rate_limit` decorator (max 60 req/min).
- **Notifications**: `notifications.py` sends Slack webhook or email alerts for remote failures.
- **Cache**: LocMemCache with prefix `git-manager-cache`, timeout 300s.
- **Middleware**: `ApiMiddleware` handles token auth from `Authorization: Bearer <token>` header or `api_token` GET param.
- **Docker entrypoint**: injects SSH key, runs makemigrations+migrate, sync_repos, collectstatic, sets up cron for check_remotes, starts gunicorn.

## Configuration (`.env`)
| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | (required) | Change in production |
| `DEBUG` | `False` | |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,*` | |
| `DB_ENGINE` | `sqlite` | or `postgres` |
| `DATABASE_URL` | (optional) | If set, overrides DB_ENGINE |
| `GIT_USER_EMAIL` | `deploy@local.test` | |
| `GIT_USER_NAME` | `Git Manager` | |
| `ENABLE_SSH_SERVER` | `false` | Starts sshd in container |
| `SSH_PORT` | `2222` | |
| `API_TOKEN` | (optional) | Bearer token auth |
| `SLACK_WEBHOOK_URL` | (optional) | Webhook URL for alerts |
| `ALERT_EMAIL_TO` | (optional) | Email recipient for alerts |

## URLs
```
/                          — Dashboard
/repos/                    — Repo list
/repos/<pk>/               — Repo detail
/remotes/                  — Remote management
/monitors/                 — Remote monitoring
/logs/                     — Push log history
/ssh/                      — SSH key management
/api/health/               — Health check
/api/status/               — Status JSON
/api/repos/ids/            — Repo IDs JSON
/api/repos/<pk>/ssh/       — SSH config JSON
/api/check-remotes/        — Trigger remote check
```
