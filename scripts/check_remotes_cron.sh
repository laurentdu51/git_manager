#!/bin/bash
# Script à placer dans crontab pour la vérification périodique des remotes
# Usage dans crontab (toutes les 15 minutes):
#   */15 * * * * /chemin/vers/scripts/check_remotes_cron.sh

set -e

cd "$(dirname "$0")/.."

# Activer l'environnement virtuel s'il existe
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "venv2" ]; then
    source venv2/bin/activate
fi

python manage.py check_remotes --alerts-only >> /var/log/git_manager_cron.log 2>&1
