import os
from django.core.management.base import BaseCommand
from django.conf import settings
from git_manager.models import GitRepo


class Command(BaseCommand):
    help = 'Synchronise les dépôts Git du dossier configuré avec la base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les dépôts sans les créer',
        )

    def handle(self, *args, **options):
        # Dans le conteneur, les dépôts sont montés sur /repos
        repos_path = '/repos'
        dry_run = options.get('dry_run', False)

        self.stdout.write(f'📁 Scan du dossier: {repos_path}')

        if not os.path.isdir(repos_path):
            self.stdout.write(self.style.ERROR(f'❌ Le dossier {repos_path} n\'existe pas'))
            return

        # Liste tous les dossiers dans repos_path
        added = 0
        skipped = 0

        for item in os.listdir(repos_path):
            item_path = os.path.join(repos_path, item)

            # Vérifie si c'est un dossier (ou un submodule git)
            if not os.path.isdir(item_path):
                continue

            # Vérifie si c'est un dépôt git (contient .git)
            is_git = os.path.isdir(os.path.join(item_path, '.git')) or os.path.isfile(os.path.join(item_path, '.git'))

            if not is_git:
                skipped += 1
                continue

            # Crée ou récupère le dépôt
            if dry_run:
                self.stdout.write(f'  [DRY-RUN] ➕ {item} → {item_path}')
                added += 1
            else:
                repo, created = GitRepo.objects.get_or_create(
                    name=item,
                    defaults={
                        'path': item_path,
                        'is_active': True,
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Ajouté: {item}'))
                    added += 1
                else:
                    self.stdout.write(f'  ⏭️  Existant: {item}')
                    # Met à jour le chemin si nécessaire
                    if repo.path != item_path:
                        repo.path = item_path
                        repo.save()
                        self.stdout.write(self.style.WARNING(f'  🔄 Chemin mis à jour: {item}'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ Terminé: {added} dépôt(s) ajouté(s), {skipped} Ignoré(s)'))