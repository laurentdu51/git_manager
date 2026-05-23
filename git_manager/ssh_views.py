from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import SshKey, GitRemote
from . import ssh_service
import logging

logger = logging.getLogger('git_manager')


def _sync_all_keys():
    physical_keys = {k['name']: k for k in ssh_service.list_all_keys()}
    for name, k in physical_keys.items():
        SshKey.objects.update_or_create(
            name=name,
            defaults={
                'key_path': k['key_path'],
                'public_key': k['public_key'],
                'fingerprint': k['fingerprint'] or '',
            }
        )
    SshKey.objects.exclude(name__in=physical_keys.keys()).delete()


def ssh_view(request):
    _sync_all_keys()
    # Prépare la liste des remotes avec leur clé pour le check
    remotes_status = [
        {'remote': r}
        for r in GitRemote.objects.filter(is_active=True).select_related('ssh_key', 'repo').order_by('repo__name', 'name')
    ]
    return render(request, 'git_manager/ssh.html', {
        'ssh_keys': SshKey.objects.all().order_by('name'),
        'remotes_status': remotes_status,
    })


@require_POST
def generate_key(request):
    name = request.POST.get('name', '').strip().replace(' ', '_') or 'id_ed25519'
    comment = request.POST.get('comment', 'git-manager').strip() or 'git-manager'
    if SshKey.objects.filter(name=name).exists() and request.POST.get('overwrite') != 'yes':
        messages.error(request, f'❌ La clé "{name}" existe déjà. Cochez "Écraser" pour confirmer.')
        return redirect('git_manager:ssh')
    result = ssh_service.generate_key(name=name, comment=comment)
    if result['success']:
        _sync_all_keys()
        messages.success(request, f'✅ Clé "{name}" générée ! Copiez la clé publique sur GitHub.')
    else:
        messages.error(request, f'❌ {result["error"]}')
    return redirect('git_manager:ssh')


@require_POST
def upload_key(request):
    name = request.POST.get('name', '').strip().replace(' ', '_') or 'id_ed25519'
    private_key = request.POST.get('private_key', '').strip()
    if not private_key:
        messages.error(request, '❌ Clé privée vide.')
        return redirect('git_manager:ssh')
    if SshKey.objects.filter(name=name).exists() and request.POST.get('overwrite') != 'yes':
        messages.error(request, f'❌ La clé "{name}" existe déjà. Cochez "Écraser" pour confirmer.')
        return redirect('git_manager:ssh')
    result = ssh_service.upload_key(private_key_content=private_key, name=name)
    if result['success']:
        _sync_all_keys()
        messages.success(request, f'✅ Clé "{name}" importée !')
    else:
        messages.error(request, f'❌ {result["error"]}')
    return redirect('git_manager:ssh')


@require_POST
def delete_key(request, name):
    result = ssh_service.delete_key(name=name)
    if result['success']:
        SshKey.objects.filter(name=name).delete()
        messages.success(request, f'🗑 Clé "{name}" supprimée.')
    else:
        messages.error(request, f'❌ {result["error"]}')
    return redirect('git_manager:ssh')


@require_POST
def rename_key(request, name):
    """Renomme une clé SSH (fichier + entrée DB)."""
    new_name = request.POST.get('new_name', '').strip().replace(' ', '_')
    if not new_name:
        messages.error(request, '❌ Nouveau nom vide.')
        return redirect('git_manager:ssh')
    if new_name == name:
        return redirect('git_manager:ssh')
    if SshKey.objects.filter(name=new_name).exists():
        messages.error(request, f'❌ Une clé nommée "{new_name}" existe déjà.')
        return redirect('git_manager:ssh')

    result = ssh_service.rename_key(old_name=name, new_name=new_name)
    if result['success']:
        # Mettre à jour la DB + les remotes qui référencent cette clé
        key = SshKey.objects.filter(name=name).first()
        if key:
            key.name = new_name
            key.key_path = result['new_key_path']
            key.save()
            # Mettre à jour les remotes liés
            GitRemote.objects.filter(ssh_key=key).update(ssh_key=key)
        _sync_all_keys()
        messages.success(request, f'✅ Clé renommée : "{name}" → "{new_name}".')
    else:
        messages.error(request, f'❌ {result["error"]}')
    return redirect('git_manager:ssh')


def test_connection(request):
    host = request.GET.get('host', 'github.com')
    name = request.GET.get('name', 'id_ed25519')
    return JsonResponse(ssh_service.test_connection(host=host, name=name))


def show_public_key(request, name):
    key = get_object_or_404(SshKey, name=name)
    return JsonResponse({'public_key': key.public_key, 'fingerprint': key.fingerprint})