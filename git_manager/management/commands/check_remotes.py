"""
Commande Django pour vérifier l'état des remotes Git.
Usage: python manage.py check_remotes
"""
import sys
import os
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

# Ajouter le parent au path pour importer les modèles
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'git_manager.settings')

import django
django.setup()

from git_manager.models import GitRepo, GitRemote, RemoteMonitor
from git_manager.services import GitService
from git_manager.notifications import send_alerts

logger = logging.getLogger('git_manager')


class Command(BaseCommand):
    help = 'Vérifie l\'état de tous les remotes Git et stocke les résultats'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affiche les détails des vérifications',
        )
        parser.add_argument(
            '--alerts-only',
            action='store_true',
            help='Affiche uniquement les remotes avec des alertes',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        alerts_only = options.get('alerts_only', False)
        
        self.stdout.write('🔍 Vérification des remotes Git...')
        
        alerts = []
        checked = 0
        errors = 0
        
        repos = GitRepo.objects.filter(is_active=True)
        total_repos = repos.count()
        
        for repo in repos:
            if not os.path.exists(repo.path):
                self.stdout.write(self.style.WARNING(f'  ⚠️ Chemin introuvable: {repo.path}'))
                errors += 1
                continue
                
            svc = GitService(repo.path)
            
            for remote in repo.remotes.filter(is_active=True):
                checked += 1
                
                try:
                    # Fetch pour avoir les dernières infos
                    fetch_result = svc.fetch(remote.name)
                    if not fetch_result['success']:
                        self.stdout.write(self.style.WARNING(f'  ⚠️ Fetch failed: {remote.name} — {fetch_result["stderr"]}'))
                        continue
                    
                    # Vérifier ahead/behind
                    result = svc.get_ahead_behind(remote.name, remote.branch)
                    
                    status = result.get('status', 'unknown')
                    ahead = result.get('ahead', 0)
                    behind = result.get('behind', 0)
                    
                    # Mettre à jour le monitor
                    with transaction.atomic():
                        monitor, _ = RemoteMonitor.objects.get_or_create(remote=remote)
                        monitor.commits_ahead = ahead
                        monitor.commits_behind = behind
                        monitor.status = status
                        monitor.last_check = timezone.now()
                        monitor.last_error = '' if result.get('success', True) else result.get('error', '')
                        monitor.save()
                    
                    # Afficher selon les options
                    if status != 'ok':
                        alerts.append({
                            'repo': repo.name,
                            'remote': remote.name,
                            'branch': remote.branch,
                            'status': status,
                            'ahead': ahead,
                            'behind': behind,
                        })
                        
                        if verbose or alerts_only:
                            emoji = {
                                'ahead': '⬆️',
                                'behind': '⬇️',
                                'diverged': '⚠️',
                            }.get(status, '❓')
                            self.stdout.write(
                                f'  {emoji} {repo.name}/{remote.name} → {status} '
                                f'(ahead={ahead}, behind={behind})'
                            )
                    else:
                        if verbose and not alerts_only:
                            self.stdout.write(f'  ✅ {repo.name}/{remote.name} → OK')
                            
                except Exception as e:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f'  ❌ Erreur {remote.name}: {e}'))
                    logger.error(f'Erreur check remote {remote.name}: {e}')
        
        # Résumé
        self.stdout.write('')
        self.stdout.write(f'📊 Résumé: {checked} remotes vérifiés, {len(alerts)} alertes, {errors} erreurs')
        
        if alerts:
            self.stdout.write(self.style.WARNING(f'⚠️ {len(alerts)} remote(s) nécessitent attention:'))
            for a in alerts:
                self.stdout.write(f'   - {a["repo"]}/{a["remote"]} ({a["branch"]}): {a["status"]}')
        
        # Envoyer les notifications si des alertes
        if alerts:
            send_alerts(alerts)

        # Retourner un code d'erreur si des alertes
        return len(alerts)