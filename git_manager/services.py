import subprocess
import os
import logging
from pathlib import Path
from django.core.cache import cache

logger = logging.getLogger('git_manager')


class GitService:
    def __init__(self, repo_path: str, ssh_key_path: str = None):
        if not repo_path or not isinstance(repo_path, str):
            raise ValueError("repo_path must be a non-empty string")
        self.repo_path = Path(repo_path).expanduser().resolve()
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Path does not exist: {self.repo_path}")
        self.ssh_key_path = ssh_key_path

    def _run(self, cmd: list) -> dict:
        env = os.environ.copy()
        if self.ssh_key_path:
            key = str(Path(self.ssh_key_path).expanduser())
            env['GIT_SSH_COMMAND'] = f'ssh -i {key} -o IdentitiesOnly=yes'
        try:
            result = subprocess.run(
                cmd, cwd=str(self.repo_path),
                capture_output=True, text=True, env=env, timeout=60,
            )
            if not result.returncode == 0:
                logger.warning(f"Git {' '.join(cmd)} — {result.stderr.strip()}")
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'stdout': '', 'stderr': 'Timeout (60s)'}
        except Exception as e:
            return {'success': False, 'stdout': '', 'stderr': str(e)}

    def is_git_repo(self) -> bool:
        return self._run(['git', 'rev-parse', '--is-inside-work-tree'])['success']

    def get_status(self) -> dict:
        return self._run(['git', 'status', '--porcelain', '-b'])

    def get_current_branch(self) -> str:
        r = self._run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        return r['stdout'] if r['success'] else 'unknown'

    def get_last_commit(self) -> dict:
        r = self._run(['git', 'log', '-1', '--format=%H|%s|%an|%ar'])
        if r['success'] and r['stdout']:
            parts = r['stdout'].split('|')
            if len(parts) >= 2:
                commit_hash = parts[0]
                commit_message = parts[1] if len(parts) > 1 else ''
                return {
                    'hash': commit_hash[:7] if commit_hash else '',
                    'full_hash': commit_hash,
                    'message': commit_message,
                    'author': parts[2] if len(parts) > 2 else '',
                    'date': parts[3] if len(parts) > 3 else '',
                }
        return {'hash': '', 'full_hash': '', 'message': '', 'author': '', 'date': ''}

    def get_remotes(self) -> list:
        r = self._run(['git', 'remote', '-v'])
        remotes = {}
        if r['success']:
            for line in r['stdout'].splitlines():
                parts = line.split()
                if len(parts) >= 2 and '(fetch)' in line:
                    remotes[parts[0]] = parts[1]
        return [{'name': k, 'url': v} for k, v in remotes.items()]

    def add_remote(self, name: str, url: str) -> dict:
        check = self._run(['git', 'remote', 'get-url', name])
        if check['success']:
            return self._run(['git', 'remote', 'set-url', name, url])
        return self._run(['git', 'remote', 'add', name, url])

    def fetch(self, remote: str = None) -> dict:
        """Fetch les références Git depuis un remote ou tous les remotes."""
        cmd = ['git', 'fetch']
        if remote:
            cmd.append(remote)
        else:
            cmd.append('--all')
        return self._run(cmd)

    def remove_remote(self, name: str) -> dict:
        return self._run(['git', 'remote', 'remove', name])

    def pull(self, remote: str, branch: str = None) -> dict:
        """Pull les changements depuis un remote."""
        if not remote:
            return {'success': False, 'stdout': '', 'stderr': 'Remote is required'}

        current_branch = self.get_current_branch()
        if current_branch == 'unknown':
            return {'success': False, 'stdout': '', 'stderr': 'Unable to determine current branch'}

        target_branch = branch or current_branch

        self._run(['git', 'config', 'pull.rebase', 'false'])
        self._run(['git', 'merge', '--abort'])  # Nettoie un éventuel merge précédent

        cmd = ['git', 'pull', remote, target_branch]
        logger.info(f"Pull {remote}/{target_branch}")
        result = self._run(cmd)
        if not result['success'] and 'unrelated histories' in result['stderr']:
            cmd.append('--allow-unrelated-histories')
            logger.info(f"Pull retry with --allow-unrelated-histories: {remote}/{target_branch}")
            result = self._run(cmd)
        if result['success']:
            logger.info(f"Pull OK: {remote}/{target_branch}")
        else:
            logger.error(f"Pull FAIL: {remote}/{target_branch} — {result['stderr']}")
        return result

    def push(self, remote: str, branch: str, force: bool = False) -> dict:
        if not remote or not branch:
            return {'success': False, 'stdout': '', 'stderr': 'Remote and branch are required'}
        current_branch = self.get_current_branch()
        if current_branch == 'unknown':
            return {'success': False, 'stdout': '', 'stderr': 'Unable to determine current branch'}
        cmd = ['git', 'push', remote, f'{current_branch}:{branch}']
        if force:
            cmd.append('--force-with-lease')
        logger.info(f"Push {remote}/{branch} (force={force})")
        result = self._run(cmd)
        if result['success']:
            logger.info(f"Push OK: {remote}/{branch}")
        else:
            logger.error(f"Push FAIL: {remote}/{branch} — {result['stderr']}")
        return result

    def create_backup_tag(self) -> dict:
        from datetime import datetime
        tag_name = f'backup-{datetime.now():%Y%m%d-%H%M%S}'
        result = self._run(['git', 'tag', '-f', tag_name])
        if result['success']:
            logger.info(f"Backup tag created: {tag_name}")
        else:
            logger.warning(f"Backup tag failed: {result['stderr']}")
        return {**result, 'tag': tag_name}

    def get_log(self, n: int = 10) -> list:
        r = self._run(['git', 'log', f'-{n}', '--format=%H|%s|%an|%ar|%ad', '--date=short'])
        commits = []
        if r['success']:
            for line in r['stdout'].splitlines():
                p = line.split('|', 4)
                if len(p) >= 4:
                    commits.append({
                        'hash': p[0][:7], 'full_hash': p[0],
                        'message': p[1], 'author': p[2],
                        'date_relative': p[3], 'date': p[4] if len(p) > 4 else '',
                    })
        return commits

    def get_ahead_behind(self, remote: str, branch: str = 'main') -> dict:
        """Retourne le nombre de commits ahead/behind par rapport au remote."""
        if not remote or not branch:
            return {'success': False, 'ahead': 0, 'behind': 0, 'status': 'error', 'stderr': 'Remote and branch are required'}

        fetch_result = self.fetch(remote)
        if not fetch_result['success']:
            return {'success': False, 'ahead': 0, 'behind': 0, 'status': 'error', 'stderr': fetch_result['stderr']}

        check_remote = self._run(['git', 'rev-parse', f'{remote}/{branch}'])
        if not check_remote['success']:
            return {'success': False, 'ahead': 0, 'behind': 0, 'status': 'error', 'stderr': f'Remote branch {remote}/{branch} not found'}

        r = self._run(['git', 'rev-list', f'{remote}/{branch}...HEAD', '--count'])
        ahead = int(r['stdout']) if r['success'] and r['stdout'].isdigit() else 0

        r = self._run(['git', 'rev-list', f'HEAD...{remote}/{branch}', '--count'])
        behind = int(r['stdout']) if r['success'] and r['stdout'].isdigit() else 0

        if ahead > 0 and behind > 0:
            status = 'diverged'
        elif ahead > 0:
            status = 'ahead'
        elif behind > 0:
            status = 'behind'
        else:
            status = 'ok'

        return {'success': True, 'ahead': ahead, 'behind': behind, 'status': status}

    def get_ahead_behind_cached(self, remote: str, branch: str = 'main', timeout: int = 300) -> dict:
        """Version cached de get_ahead_behind."""
        cache_key = f'git_ahead_behind_{self.repo_path}_{remote}_{branch}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        result = self.get_ahead_behind(remote, branch)
        cache.set(cache_key, result, timeout)
        return result


    def list_remote_branches(self) -> list:
        """Liste les branches distantes (remote-tracking) triées par remote."""
        r = self._run(['git', 'branch', '-r', '-v', '--no-color'])
        branches = []
        if not r['success']:
            return branches
        for line in r['stdout'].splitlines():
            line = line.strip()
            if not line:
                continue
            # Format : "remote/branch    hash message"
            parts = line.split(None, 2)
            if len(parts) >= 2:
                full_name = parts[0]
                commit_hash = parts[1][:7]
                commit_msg = parts[2] if len(parts) > 2 else ''
                slash = full_name.find('/')
                if slash > 0:
                    remote_name = full_name[:slash]
                    branch_name = full_name[slash+1:]
                else:
                    remote_name = full_name
                    branch_name = full_name
                branches.append({
                    'full_name': full_name,
                    'remote': remote_name,
                    'branch': branch_name,
                    'hash': commit_hash,
                    'message': commit_msg,
                })
        return branches


def clone_repo(url: str, target_path: str, ssh_key_path: str = None,
               remote_name: str = 'origin') -> dict:
    """Clone un dépôt distant en local.

    Crée le dossier parent si nécessaire, exécute ``git clone``,
    puis applique la configuration standard du gestionnaire.
    """
    repo_path = Path(target_path).expanduser().resolve()
    parent = repo_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {'success': False, 'error': f"Impossible de créer le dossier parent : {e}"}

    env = os.environ.copy()
    if ssh_key_path:
        key = str(Path(ssh_key_path).expanduser())
        env['GIT_SSH_COMMAND'] = f'ssh -i {key} -o IdentitiesOnly=yes'

    cmd = ['git', 'clone', '--origin', remote_name, url, str(repo_path)]
    logger.info(f"Clone {url} → {repo_path}")
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True, env=env)
    except subprocess.CalledProcessError as e:
        return {'success': False, 'error': e.stderr.strip() or str(e)}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Timeout (120s)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

    _git_config(repo_path, 'receive.denyCurrentBranch', 'updateInstead')
    _git_config(repo_path, 'pull.rebase', 'false')
    _git_config(repo_path, 'user.email', 'deploy@local.test')
    _git_config(repo_path, 'user.name', 'Git Manager')

    logger.info(f"Clone terminé : {url} → {repo_path}")
    return {'success': True, 'path': str(repo_path)}


def init_repo(path: str, default_branch: str = 'main') -> dict:
    """Crée un nouveau dépôt Git vide à l'emplacement donné.

    Crée le dossier si nécessaire, exécute ``git init``,
    configure l'utilisateur et autorise les pushes sur la branche courante.
    """
    repo_path = Path(path).expanduser().resolve()
    try:
        repo_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {'success': False, 'error': f"Impossible de créer le dossier : {e}"}

    try:
        subprocess.run(
            ['git', 'init', f'--initial-branch={default_branch}'],
            cwd=str(repo_path), capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        return {'success': False, 'error': f"git init a échoué : {e.stderr or e}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}

    # Permet les pushes vers la branche courante (utile pour le relai SSH)
    _git_config(repo_path, 'receive.denyCurrentBranch', 'updateInstead')
    # Stratégie pull : merge plutôt que rebase (évite l'erreur "divergent branches")
    _git_config(repo_path, 'pull.rebase', 'false')
    # Identité du gestionnaire
    _git_config(repo_path, 'user.email', 'deploy@local.test')
    _git_config(repo_path, 'user.name', 'Git Manager')

    # Commit initial pour établir la branche (sinon push refuse)
    try:
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', 'Initial commit'],
            cwd=str(repo_path), capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        return {'success': False, 'error': f"Commit initial a échoué : {e.stderr or e}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}

    logger.info(f"Nouveau dépôt initialisé : {repo_path}")
    return {'success': True, 'path': str(repo_path)}


def _git_config(repo_path: Path, key: str, value: str) -> None:
    """Helper : exécute ``git config <key> <value>`` dans le dépôt."""
    try:
        subprocess.run(
            ['git', 'config', key, value],
            cwd=str(repo_path), capture_output=True, text=True, timeout=15, check=True,
        )
    except Exception:
        logger.warning(f"git config {key} a échoué (ignoré)")
