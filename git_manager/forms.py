import re
from django import forms
from django.core.exceptions import ValidationError
from pathlib import Path


def validate_repo_name(value):
    if not value or len(value) < 2:
        raise ValidationError('Le nom doit contenir au moins 2 caractères.')
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValidationError('Le nom ne peut contenir que des lettres, chiffres, tirets et underscores.')


def validate_git_path(value):
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise ValidationError('Le chemin spécifié n\'existe pas.')
    if not path.is_dir():
        raise ValidationError('Le chemin doit être un répertoire.')


def validate_remote_name(value):
    if not value or len(value) < 1:
        raise ValidationError('Le nom du remote est obligatoire.')
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValidationError('Le nom ne peut contenir que des lettres, chiffres, tirets et underscores.')


def validate_git_url(value):
    if not value:
        raise ValidationError('L\'URL est obligatoire.')
    url_pattern = r'^(https?://|git@|ssh://|git://)'
    if not re.match(url_pattern, value):
        raise ValidationError('URL invalide. Utilisez http://, https://, git@, ssh:// ou git://')


def validate_ssh_key_path(value):
    if not value:
        return
    path = Path(value).expanduser()
    if not path.exists():
        raise ValidationError('Le fichier de clé SSH n\'existe pas.')
    if not path.name in ['id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa'] and not path.name.startswith('id_'):
        raise ValidationError('Le fichier ne semble pas être une clé SSH valide.')


class SshKeyForm(forms.Form):
    name = forms.CharField(max_length=100, validators=[validate_repo_name])
    key_path = forms.CharField(max_length=500, required=False, validators=[validate_ssh_key_path])


class GitRepoForm(forms.Form):
    name = forms.CharField(max_length=100, validators=[validate_repo_name])
    path = forms.CharField(max_length=500, validators=[validate_git_path])
    description = forms.CharField(widget=forms.Textarea, required=False)


class GitRemoteForm(forms.Form):
    name = forms.CharField(max_length=100, validators=[validate_remote_name])
    url = forms.CharField(max_length=500, validators=[validate_git_url])
    branch = forms.CharField(max_length=100, required=False)
    use_force = forms.BooleanField(required=False)
    ssh_key_id = forms.IntegerField(required=False)