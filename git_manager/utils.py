import os
from django.conf import settings


def detect_server_ip(request) -> str:
    """Détecte l'IP du serveur à partir de la requête."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    host = request.META.get('HTTP_HOST', '')
    if ':' in host:
        return host.split(':')[0]
    return host or request.META.get('SERVER_NAME', '127.0.0.1')


def detect_ssh_port() -> int:
    """Détecte le port SSH à partir des variables d'environnement."""
    try:
        return int(os.environ.get('SSH_PORT', 2222))
    except ValueError:
        return 2222