# Git Manager

Relai Git multi-dépôts avec interface web, gestion de clés SSH, surveillance de remotes et notifications.

## Architecture

```
Machine locale  ── git push ──▶  Git Manager (relai)  ── git push ──▶  GitHub/GitLab
                                      │
                                 ┌────┴────┐
                                 │   Web   │  Dashboard, logs, monitoring
                                 ├─────────┤
                                 │   API   │  Status, SSH config (rate-limited)
                                 ├─────────┤
                                 │  SSH    │  Server relai (port 2222)
                                 └─────────┘
```

## Stack

- Python 3.12 / Django 4.2
- SQLite (PostgreSQL optionnel)
- Gunicorn + Whitenoise
- Docker / docker-compose
- Aucun framework JS — vanilla JS + CSS inline

## Démarrage rapide

```bash
cp .env.example .env
# Éditer .env : SECRET_KEY, REPOS_PATH, etc.
docker compose up -d --build
```

Accès : `http://localhost:8000`

## Configuration

| Variable | Défaut | Description |
|----------|--------|-------------|
| `SECRET_KEY` | — | Clé secrète Django (obligatoire) |
| `DEBUG` | `False` | Mode debug |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hôtes autorisés |
| `REPOS_PATH` | — | Chemin hôte des dépôts Git à monter |
| `SQLITE_PATH` | `/app/data/db.sqlite3` | Base SQLite |
| `DATABASE_URL` | — | PostgreSQL (optionnel, écrase SQLite) |
| `ENABLE_SSH_SERVER` | `false` | Activer le serveur SSH relai |
| `SSH_PORT` | `2222` | Port SSH externe |
| `API_TOKEN` | — | Token Bearer pour les endpoints API |
| `SLACK_WEBHOOK_URL` | — | Webhook Slack pour alertes |
| `ALERT_EMAIL_TO` | — | Email pour alertes |
| `CRON_SCHEDULE` | `*/15 * * * *` | Fréquence `check_remotes` |

## Commandes

```bash
# Vérifier l'état des remotes
python manage.py check_remotes [--verbose] [--alerts-only]

# Synchroniser les dépôts du dossier /repos
python manage.py sync_repos [--dry-run]

# Planification cron (hors Docker)
echo "*/15 * * * * $(pwd)/scripts/check_remotes_cron.sh" | crontab -
```

## Tests

```bash
python manage.py test --verbosity=2
```

75 tests : forms, models, services, vues, middleware.

## API

| Endpoint | Rate limit | Auth | Description |
|----------|-----------|------|-------------|
| `GET /api/health/` | — | — | Healthcheck |
| `GET /api/status/` | 30/min | Token | Statut de tous les dépôts |
| `GET /api/repos/ids/` | 60/min | Token | Liste id/name des dépôts |
| `GET /api/repos/<pk>/ssh/` | 30/min | Token | Config SSH pour un dépôt |
| `GET /api/check-remotes/` | 10/min | Login | Vérification des remotes (login requis) |

L'authentification API se fait via header : `Authorization: Bearer <token>`

## Fonctionnalités

- **Dashboard** — Vue d'ensemble des dépôts, statuts git, push rapide
- **Gestion de dépôts** — Ajout/suppression, détection automatique depuis `/repos/`
- **Remotes** — Ajout/édition/suppression, push/pull/fetch, test SSH
- **Clés SSH** — Génération, import, renommage, suppression, association aux remotes
- **Surveillance** — Vérification périodique des remotes (ahead/behind/diverged), notifications Slack/email
- **Logs** — Historique des actions, filtrage par statut, logs applicatifs
- **SSH Local** — Guide de configuration pour connexion locale → relai → GitHub
- **Backup auto** — Tag git `backup-YYYYMMDD-HHMMSS` avant chaque push
- **Thème dark/light** — Toggle sauvegardé dans localStorage
