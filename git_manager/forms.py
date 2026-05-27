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


class CreateRepoForm(forms.Form):
    name = forms.CharField(max_length=100, validators=[validate_repo_name])
    path = forms.CharField(
        max_length=500,
        help_text='Chemin où créer le dépôt (ex. /repos/mon-projet).',
    )
    description = forms.CharField(widget=forms.Textarea, required=False)

    def clean_path(self):
        path = self.cleaned_data['path'].strip()
        resolved = Path(path).expanduser().resolve()
        # Si le chemin existe déjà et contient déjà un .git, on prévient
        git_dir = resolved / '.git'
        if resolved.exists() and (git_dir.is_dir() or git_dir.is_file()):
            raise ValidationError(
                'Un dépôt Git existe déjà à cet emplacement. '
                'Utilisez "Ajouter un dépôt" pour l\'importer.'
            )
        return str(resolved)


class CloneRepoForm(forms.Form):
    remote_url = forms.CharField(
        max_length=500, validators=[validate_git_url],
        label='URL du dépôt distant',
        help_text='git@github.com:user/projet.git ou https://github.com/user/projet.git',
    )
    name = forms.CharField(max_length=100, validators=[validate_repo_name])
    ssh_key_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    description = forms.CharField(widget=forms.Textarea, required=False)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        return name

    def clean_remote_url(self):
        url = self.cleaned_data['remote_url'].strip()
        return url


class GitRemoteForm(forms.Form):
    name = forms.CharField(max_length=100, validators=[validate_remote_name])
    url = forms.CharField(max_length=500, validators=[validate_git_url])
    branch = forms.CharField(max_length=100, required=False)
    use_force = forms.BooleanField(required=False)
    ssh_key_id = forms.IntegerField(required=False)