import logging
import os
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings

from .models import GitRepo, GitRemote, PushLog, SshKey
from .services import GitService
from . import ssh_service
from .utils import detect_server_ip, detect_ssh_port
from .middleware import rate_limit, api_auth_required

logger = logging.getLogger('git_manager')
LOG_FILE = settings.LOG_FILE


def _sync_remotes_to_git(repo, svc):
    """Synchronise tous les remotes DB → git pour ce dépôt."""
    for remote in repo.remotes.filter(is_active=True):
        result = svc.add_remote(remote.name, remote.url)
        if result['success']:
            logger.info(f"Remote synced: {repo.name} → {remote.name} ({remote.url})")
        else:
            logger.warning(f"Remote sync warning [{remote.name}]: {result['stderr']}")

# ── Dashboard ─────────────────────────────────────────────────────────────

def dashboard(request):
    repos = GitRepo.objects.filter(is_active=True).prefetch_related('remotes')
    repos_data = []
    for repo in repos:
        svc = GitService(repo.path)
        is_git = svc.is_git_repo()
        repos_data.append({
            'repo': repo,
            'is_git': is_git,
            'branch': svc.get_current_branch() if is_git else None,
            'last_commit': svc.get_last_commit() if is_git else None,
            'status': svc.get_status() if is_git else None,
            'remotes': repo.remotes.filter(is_active=True),
        })
    return render(request, 'git_manager/dashboard.html', {
        'repos_data': repos_data,
        'recent_logs': PushLog.objects.all()[:15],
        'total_pushes': PushLog.objects.count(),
        'success_pushes': PushLog.objects.filter(status='success').count(),
        'error_pushes': PushLog.objects.filter(status='error').count(),
        'total_repos': GitRepo.objects.filter(is_active=True).count(),
    })

# ── Repos ─────────────────────────────────────────────────────────────────

def repos_view(request):
    return render(request, 'git_manager/repos.html', {
        'repos': GitRepo.objects.prefetch_related('remotes').all()
    })


def repo_detail(request, pk):
    repo = get_object_or_404(GitRepo, pk=pk)
    svc = GitService(repo.path)
    is_git = svc.is_git_repo()
    server_ip = detect_server_ip(request)
    ssh_port = detect_ssh_port()
    remotes = repo.remotes.select_related('ssh_key').all()
    push_logs = PushLog.objects.filter(repo=repo).select_related('remote')[:20]
    git_log = svc.get_log(10) if is_git else []

    return render(request, 'git_manager/repo_detail.html', {
        'repo': repo,
        'is_git': is_git,
        'branch': svc.get_current_branch() if is_git else None,
        'last_commit': svc.get_last_commit() if is_git else None,
        'git_status': svc.get_status() if is_git else None,
        'git_log': git_log,
        'remotes': remotes,
        'push_logs': push_logs,
        'server_ip': server_ip,
        'ssh_port': ssh_port,
        'ssh_keys': SshKey.objects.all(),
        'relay_remote_cmd': f"git remote add relay ssh://root@{server_ip}:{ssh_port}{repo.path}"
    })

@require_POST
def add_repo(request):
    from .forms import GitRepoForm
    name = request.POST.get('name', '').strip()
    path = request.POST.get('path', '').strip()
    description = request.POST.get('description', '').strip()

    form = GitRepoForm({'name': name, 'path': path, 'description': description})
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect('git_manager:repos')

    try:
        svc = GitService(path)
        if not svc.is_git_repo():
            messages.error(request, f'❌ Aucun dépôt Git trouvé dans : {path}')
            return redirect('git_manager:repos')
    except (ValueError, FileNotFoundError) as e:
        messages.error(request, str(e))
        return redirect('git_manager:repos')

    repo, _ = GitRepo.objects.update_or_create(
        name=name, defaults={'path': path, 'description': description, 'is_active': True}
    )
    logger.info(f"Repo added: {name} at {path}")
    messages.success(request, f'✅ Dépôt "{name}" ajouté.')
    return redirect('git_manager:repo_detail', pk=repo.pk)

@require_POST
def create_repo(request):
    from .forms import CreateRepoForm
    from .services import init_repo

    name = request.POST.get('name', '').strip()
    path = request.POST.get('path', '').strip()
    description = request.POST.get('description', '').strip()

    form = CreateRepoForm({'name': name, 'path': path, 'description': description})
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect('git_manager:repos')

    # Initialiser le dépôt Git
    result = init_repo(path)
    if not result['success']:
        messages.error(request, f'❌ Échec de la création : {result["error"]}')
        return redirect('git_manager:repos')

    try:
        repo = GitRepo.objects.create(
            name=name, path=result['path'], description=description, is_active=True
        )
    except Exception as e:
        # Nettoyer le dossier créé en cas d'erreur DB
        import shutil
        try:
            shutil.rmtree(result['path'])
        except Exception:
            pass
        messages.error(request, f'❌ Erreur lors de l\'enregistrement : {e}')
        return redirect('git_manager:repos')

    logger.info(f"Repo created: {name} at {result['path']}")
    messages.success(request, f'✅ Nouveau dépôt "{name}" créé.')
    return redirect('git_manager:repo_detail', pk=repo.pk)


@require_POST
def delete_repo(request, pk):
    repo = get_object_or_404(GitRepo, pk=pk)
    name = repo.name
    repo.delete()
    logger.info(f"Repo deleted: {name}")
    messages.success(request, f'Dépôt "{name}" supprimé.')
    return redirect('git_manager:repos')

# ── Remotes ───────────────────────────────────────────────────────────────

def remotes_view(request):
    return render(request, 'git_manager/remotes.html', {
        'repos': GitRepo.objects.prefetch_related('remotes__ssh_key').all(),
        'ssh_keys': SshKey.objects.all(),
        'key_exists': ssh_service.key_exists()
    })

@require_POST
def add_remote(request):
    from .forms import GitRemoteForm
    repo = get_object_or_404(GitRepo, pk=request.POST.get('repo_id'))
    name = request.POST.get('name', '').strip()
    url = request.POST.get('url', '').strip()
    branch = request.POST.get('branch', 'main').strip()
    use_force = request.POST.get('use_force') == 'on'
    ssh_key_id = request.POST.get('ssh_key_id') or None

    form = GitRemoteForm({'name': name, 'url': url, 'branch': branch, 'use_force': use_force, 'ssh_key_id': ssh_key_id})
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect('git_manager:remotes')

    ssh_key = SshKey.objects.filter(pk=ssh_key_id).first() if ssh_key_id else None
    try:
        svc = GitService(repo.path, ssh_key.key_path if ssh_key else None)
        result = svc.add_remote(name, url)
        if not result['success']:
            messages.error(request, f"Erreur Git : {result['stderr']}")
            return redirect('git_manager:remotes')
    except (ValueError, FileNotFoundError) as e:
        messages.error(request, str(e))
        return redirect('git_manager:remotes')

    GitRemote.objects.update_or_create(
        repo=repo, name=name,
        defaults={'url': url, 'branch': branch, 'use_force': use_force, 'is_active': True, 'ssh_key': ssh_key}
    )
    logger.info(f"Remote added: {repo.name} → {name}")
    messages.success(request, f'✅ Remote "{name}" ajouté à "{repo.name}".')
    return redirect('git_manager:repo_detail', pk=repo.pk)


def edit_remote(request, pk):
    remote = get_object_or_404(GitRemote, pk=pk)
    if request.method == 'POST':
        remote.url = request.POST.get('url', remote.url).strip()
        remote.branch = request.POST.get('branch', remote.branch).strip()
        remote.use_force = request.POST.get('use_force') == 'on'
        ssh_key_id = request.POST.get('ssh_key_id') or None
        remote.ssh_key = SshKey.objects.filter(pk=ssh_key_id).first() if ssh_key_id else None
        remote.save()
        GitService(remote.repo.path).add_remote(remote.name, remote.url)
        logger.info(f"Remote updated: {remote.repo.name} → {remote.name}")
        messages.success(request, f'✅ Remote "{remote.name}" mis à jour.')
        return redirect('git_manager:repo_detail', pk=remote.repo.pk)
    return render(request, 'git_manager/remote_edit.html', {
        'remote': remote,
        'ssh_keys': SshKey.objects.all(),
    })

@require_POST
def delete_remote(request, pk):
    remote = get_object_or_404(GitRemote, pk=pk)
    repo_pk = remote.repo.pk
    GitService(remote.repo.path).remove_remote(remote.name)
    name = remote.name
    remote.delete()
    logger.info(f"Remote deleted: {name}")
    messages.success(request, f'Remote "{name}" supprimé.')
    return redirect('git_manager:repo_detail', pk=repo_pk)


def test_remote(request, pk):
    remote = get_object_or_404(GitRemote, pk=pk)
    key_path = remote.ssh_key.key_path if remote.ssh_key else None
    result = ssh_service.test_connection_for_remote(remote.url, key_path)
    # Log the action
    PushLog.objects.create(
        repo=remote.repo,
        remote=remote,
        action='test',
        repo_name=remote.repo.name,
        remote_name=remote.name,
        branch=remote.branch,
        status='success' if result['success'] else 'error',
        output=result.get('output', ''),
        error_output=result.get('error', ''),
        triggered_by='manual',
    )
    return JsonResponse(result)


def fetch_remote(request, pk):
    remote = get_object_or_404(GitRemote, pk=pk)
    key_path = remote.ssh_key.key_path if remote.ssh_key else None
    svc = GitService(remote.repo.path, key_path)
    result = svc.fetch(remote.name)
    # Log the action
    PushLog.objects.create(
        repo=remote.repo,
        remote=remote,
        action='fetch',
        repo_name=remote.repo.name,
        remote_name=remote.name,
        branch=remote.branch,
        status='success' if result['success'] else 'error',
        output=result['stdout'],
        error_output=result['stderr'],
        triggered_by='manual',
    )
    return JsonResponse({
        'success': result['success'],
        'output': result['stdout'],
        'error': result['stderr'],
    })


def pull_remote(request, pk):
    remote = get_object_or_404(GitRemote, pk=pk)
    key_path = remote.ssh_key.key_path if remote.ssh_key else None
    svc = GitService(remote.repo.path, key_path)
    result = svc.pull(remote.name, remote.branch)
    PushLog.objects.create(
        repo=remote.repo,
        remote=remote,
        action='pull',
        repo_name=remote.repo.name,
        remote_name=remote.name,
        branch=remote.branch,
        status='success' if result['success'] else 'error',
        output=result['stdout'],
        error_output=result['stderr'],
        triggered_by='manual',
    )
    return JsonResponse({
        'success': result['success'],
        'output': result['stdout'],
        'error': result['stderr'],
    })

# ── Push ──────────────────────────────────────────────────────────────────
@require_POST
def push_now(request):
    remote = get_object_or_404(GitRemote, pk=request.POST.get('remote_id'))
    repo = remote.repo
    key_path = remote.ssh_key.key_path if remote.ssh_key else None
    svc = GitService(repo.path, key_path)

    # Sync tous les remotes DB → git avant de pusher
    _sync_remotes_to_git(repo, svc)

    # Backup tag avant push
    backup = svc.create_backup_tag()

    log = PushLog.objects.create(
        repo=repo, remote=remote, repo_name=repo.name,
        remote_name=remote.name, branch=remote.branch,
        status='pending', triggered_by='manual',
    )
    last = svc.get_last_commit()
    log.commit_hash = last.get('full_hash', '')
    log.commit_message = last.get('message', '')

    result = svc.push(remote.name, remote.branch, remote.use_force)
    log.status = 'success' if result['success'] else 'error'
    log.output = result['stdout']
    log.error_output = result['stderr']
    log.save()

    if result['success']:
        backup_msg = f" (tag: {backup['tag']})" if backup['success'] else ''
        messages.success(request, f'✅ Push "{repo.name}" → "{remote.name}/{remote.branch}" réussi !{backup_msg}')
    else:
        messages.error(request, f'❌ {result["stderr"]}')

    next_url = request.POST.get('next', '')
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('git_manager:repo_detail', pk=repo.pk)

# ── Logs ──────────────────────────────────────────────────────────────────

def logs_view(request):
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    logs = PushLog.objects.all().select_related('repo', 'remote')
    status_filter = request.GET.get('status')
    if status_filter:
        logs = logs.filter(status=status_filter)

    paginator = Paginator(logs, 25)
    page = request.GET.get('page', 1)

    try:
        logs_page = paginator.page(page)
    except PageNotAnInteger:
        logs_page = paginator.page(1)
    except EmptyPage:
        logs_page = paginator.page(paginator.num_pages)

    return render(request, 'git_manager/logs.html', {
        'logs': logs_page,
        'status_filter': status_filter,
        'paginator': paginator,
    })


def file_logs_view(request):
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    lines = []
    total_lines = 0
    paginator = None

    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                total_lines = len(all_lines)
                paginator = Paginator(all_lines, 50)
                page = request.GET.get('page', 1)

                try:
                    lines = paginator.page(page).object_list
                except PageNotAnInteger:
                    lines = paginator.page(1).object_list
                except EmptyPage:
                    lines = paginator.page(paginator.num_pages).object_list
        except Exception as e:
            lines = [f'Erreur lecture log : {e}']
    else:
        lines = ["Aucun log pour l'instant."]

    return render(request, 'git_manager/file_logs.html', {
        'lines': lines,
        'total_lines': total_lines,
        'paginator': paginator,
    })


def file_logs_raw(request):
    lines = []
    if LOG_FILE.exists():
        try:
            lines = LOG_FILE.read_text(errors='replace').splitlines()[-200:]
        except:
            pass
    return JsonResponse({'lines': lines})

# ── SSH local ───────────────────────────────────────────────────────────────

def ssh_local_view(request):
    server_ip = detect_server_ip(request)
    ssh_port = detect_ssh_port()
    public_key = ssh_service.get_public_key()
    return render(request, 'git_manager/ssh_local.html', {
        'server_ip': server_ip,
        'ssh_port': ssh_port,
        'public_key': public_key,
        'ssh_keys': SshKey.objects.all(),
        'repos': GitRepo.objects.filter(is_active=True),
        'ssh_enabled': settings.ENABLE_SSH_SERVER,
        'ssh_command': f'ssh -p {ssh_port} -o StrictHostKeyChecking=no root@{server_ip}',
    })

# ── Healthcheck ──────────────────────────────────────────────────────────

def api_health(request):
    return JsonResponse({'status': 'ok'})


# ── API ───────────────────────────────────────────────────────────────────

@api_auth_required
@rate_limit(requests_per_minute=30, key_prefix='api_status')
def api_status(request):
    data = []
    for repo in GitRepo.objects.filter(is_active=True):
        svc = GitService(repo.path)
        data.append({'name': repo.name, 'path': repo.path,
                     'branch': svc.get_current_branch(), 'last_commit': svc.get_last_commit()})
    return JsonResponse({'repos': data})


@api_auth_required
@rate_limit(requests_per_minute=60, key_prefix='api_repos')
def api_repos_ids(request):
    repos = list(GitRepo.objects.filter(is_active=True).values('id', 'name'))
    return JsonResponse({'repos': repos})


@api_auth_required
@rate_limit(requests_per_minute=30, key_prefix='api_ssh')
def api_repo_ssh_config(request, pk):
    repo = get_object_or_404(GitRepo, pk=pk)
    server_ip = detect_server_ip(request)
    ssh_port = detect_ssh_port()
    remotes = repo.remotes.filter(is_active=True)
    return JsonResponse({
        'repo': repo.name,
        'server_ip': server_ip,
        'ssh_port': ssh_port,
        'relay_remote': f"ssh://root@{server_ip}:{ssh_port}{repo.path}",
        'commands': {
            'add_remote': f"git remote add relay ssh://root@{server_ip}:{ssh_port}{repo.path}",
            'push_main': "git push relay main",
        },
        'remotes': [{'name': r.name, 'url': r.url, 'branch': r.branch} for r in remotes],
    })

# ── Surveillance ─────────────────────────────────────────────────────────

@login_required
@rate_limit(requests_per_minute=10, key_prefix='check_remotes')
def check_remotes_view(request):
    """Vérifie l'état de tous les remotes et retourne les alertes."""
    from .models import RemoteMonitor
    alerts = []

    for repo in GitRepo.objects.filter(is_active=True):
        if not os.path.exists(repo.path):
            continue
        svc = GitService(repo.path)

        for remote in repo.remotes.filter(is_active=True):
            result = svc.get_ahead_behind_cached(remote.name, remote.branch, timeout=300)

            monitor, _ = RemoteMonitor.objects.get_or_create(remote=remote)
            monitor.commits_ahead = result.get('ahead', 0)
            monitor.commits_behind = result.get('behind', 0)
            monitor.status = result.get('status', 'unknown')
            monitor.last_check = timezone.now()
            monitor.save()

            if result.get('status') in ('ahead', 'behind', 'diverged'):
                alerts.append({
                    'repo': repo.name,
                    'remote': remote.name,
                    'branch': remote.branch,
                    'status': result.get('status'),
                    'ahead': result.get('ahead', 0),
                    'behind': result.get('behind', 0),
                })
    
    return JsonResponse({'alerts': alerts, 'count': len(alerts)})


@login_required
def monitors_view(request):
    """Affiche la page de surveillance des remotes."""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from .models import RemoteMonitor

    monitors = RemoteMonitor.objects.select_related('remote__repo').all()
    paginator = Paginator(monitors, 25)
    page = request.GET.get('page', 1)

    try:
        monitors_page = paginator.page(page)
    except PageNotAnInteger:
        monitors_page = paginator.page(1)
    except EmptyPage:
        monitors_page = paginator.page(paginator.num_pages)

    return render(request, 'git_manager/monitors.html', {
        'monitors': monitors_page,
        'paginator': paginator,
    })