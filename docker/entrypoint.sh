#!/bin/bash
set -e

echo "🐳 Git Manager v2 — Démarrage..."

# ── Clé SSH via variable d'env ──
if [ -n "$GIT_SSH_PRIVATE_KEY" ]; then
    echo "🔑 Injection clé SSH..."
    echo "$GIT_SSH_PRIVATE_KEY" > /root/.ssh/id_ed25519
    chmod 600 /root/.ssh/id_ed25519
    ssh-keygen -y -f /root/.ssh/id_ed25519 > /root/.ssh/id_ed25519.pub 2>/dev/null || true
    ssh-keyscan -H github.com >> /root/.ssh/known_hosts 2>/dev/null
    ssh-keyscan -H gitlab.com >> /root/.ssh/known_hosts 2>/dev/null
    cat > /root/.ssh/config << 'SSHEOF'
Host github.com
  HostName github.com
  User git
  IdentityFile /root/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking no

Host gitlab.com
  HostName gitlab.com
  User git
  IdentityFile /root/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking no
SSHEOF
    chmod 600 /root/.ssh/config
    echo "✅ Clé SSH OK."
fi

# ── Git config ──
git config --global user.email "${GIT_USER_EMAIL:-git-manager@docker.local}"
git config --global user.name "${GIT_USER_NAME:-Git Manager}"
git config --global --add safe.directory '*'

# ── SSH server (pour accès local → relai) ──
if [ "${ENABLE_SSH_SERVER:-false}" = "true" ]; then
    echo "🔐 Démarrage sshd..."
    /usr/sbin/sshd
fi

# ── Dossier data ──
mkdir -p /app/data

# ── Migrations ──
echo "📦 Migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# ── Synchronisation des dépôts ──
echo "📂 Synchronisation des dépôts..."
python manage.py sync_repos

# ── Fichiers statiques ──
echo "📁 Fichiers statiques..."
python manage.py collectstatic --noinput

# ── Configuration cron pour surveillance des remotes ──
CRON_SCHEDULE="${CRON_SCHEDULE:-*/15 * * * *}"

# Créer le répertoire crontabs s'il n'existe pas
mkdir -p /var/spool/cron/crontabs

# Créer le fichier crontab
if [ ! -f /var/spool/cron/crontabs/root ]; then
    echo "$CRON_SCHEDULE cd /app && python manage.py check_remotes --verbose >> /app/data/cron.log 2>&1" > /var/spool/cron/crontabs/root
    chmod 600 /var/spool/cron/crontabs/root
    echo "⏰ Configuration cron ($CRON_SCHEDULE)..."
    echo "Cron est démarré"
else
    echo "⏰ Cron déjà configuré"
fi

# Démarrer cron en arrière-plan
cron &

# ── Gunicorn ──
WORKERS="${GUNICORN_WORKERS:-2}"
echo "🚀 Gunicorn ($WORKERS workers) sur :8000"
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers "$WORKERS" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    config.wsgi:application