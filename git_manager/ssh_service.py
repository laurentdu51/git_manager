import subprocess
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger('git_manager')

SSH_DIR = Path('/root/.ssh')


def _ensure_ssh_dir():
    SSH_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def _key_path(name: str) -> Path:
    return SSH_DIR / name


def _pub_key_path(name: str) -> Path:
    return SSH_DIR / f'{name}.pub'


# ── Compat ancien code (clé "default" = id_ed25519) ──────────────────────
KEY_PATH = _key_path('id_ed25519')
PUB_KEY_PATH = _pub_key_path('id_ed25519')


def key_exists(name: str = 'id_ed25519') -> bool:
    return _key_path(name).exists() and _pub_key_path(name).exists()


def get_public_key(name: str = 'id_ed25519') -> Optional[str]:
    p = _pub_key_path(name)
    return p.read_text().strip() if p.exists() else None


def get_key_fingerprint(name: str = 'id_ed25519') -> Optional[str]:
    kp = _key_path(name)
    if not kp.exists():
        return None
    try:
        r = subprocess.run(
            ['ssh-keygen', '-l', '-f', str(_pub_key_path(name))],
            capture_output=True, text=True
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def list_all_keys() -> List[dict]:
    """Retourne toutes les clés privées présentes dans ~/.ssh/"""
    keys = []
    if not SSH_DIR.exists():
        return keys
    for pub in sorted(SSH_DIR.glob('*.pub')):
        priv = pub.with_suffix('')
        if not priv.exists():
            continue
        name = priv.name
        fp = None
        try:
            r = subprocess.run(['ssh-keygen', '-l', '-f', str(pub)], capture_output=True, text=True)
            fp = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            pass
        keys.append({
            'name': name,
            'key_path': str(priv),
            'pub_path': str(pub),
            'public_key': pub.read_text().strip(),
            'fingerprint': fp,
        })
    return keys


def generate_key(name: str = 'id_ed25519', comment: str = 'git-manager') -> dict:
    _ensure_ssh_dir()
    kp = _key_path(name)
    pp = _pub_key_path(name)
    try:
        kp.unlink(missing_ok=True)
        pp.unlink(missing_ok=True)
        r = subprocess.run(
            ['ssh-keygen', '-t', 'ed25519', '-C', comment, '-f', str(kp), '-N', ''],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            kp.chmod(0o600)
            _rebuild_ssh_config()
            logger.info(f"SSH key generated: {name} ({comment})")
            return {'success': True, 'public_key': pp.read_text().strip()}
        logger.error(f"SSH key gen failed [{name}]: {r.stderr}")
        return {'success': False, 'error': r.stderr}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def upload_key(private_key_content: str, name: str = 'id_ed25519') -> dict:
    _ensure_ssh_dir()
    kp = _key_path(name)
    pp = _pub_key_path(name)
    try:
        content = _normalize_private_key(private_key_content)
        if not content:
            return {'success': False, 'error': 'Format invalide. Doit commencer par -----BEGIN'}
        kp.write_text(content)
        kp.chmod(0o600)
        r = subprocess.run(['ssh-keygen', '-y', '-f', str(kp)], capture_output=True, text=True)
        if r.returncode != 0:
            err = r.stderr.strip() or 'Clé invalide ou corrompue'
            kp.unlink(missing_ok=True)
            logger.error(f"SSH upload failed [{name}]: {err}")
            return {'success': False, 'error': err}
        pp.write_text(r.stdout)
        _rebuild_ssh_config()
        logger.info(f"SSH key uploaded: {name}")
        return {'success': True, 'public_key': r.stdout.strip()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_key(name: str = 'id_ed25519') -> dict:
    try:
        _key_path(name).unlink(missing_ok=True)
        _pub_key_path(name).unlink(missing_ok=True)
        _rebuild_ssh_config()
        logger.info(f"SSH key deleted: {name}")
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def test_connection(host: str = 'github.com', name: str = 'id_ed25519') -> dict:
    return test_connection_with_key(str(_key_path(name)), host)


def test_connection_with_key(key_path: str, host: str = 'github.com') -> dict:
    kp = Path(key_path)
    if not kp.exists():
        return {'success': False, 'output': f'Clé introuvable : {kp}'}
    try:
        subprocess.run(['ssh-keyscan', '-H', host], capture_output=True, text=True, timeout=10)
        r = subprocess.run(
            ['ssh', '-T', '-i', str(kp),
             '-o', 'StrictHostKeyChecking=no',
             '-o', 'IdentitiesOnly=yes',
             f'git@{host}'],
            capture_output=True, text=True, timeout=15
        )
        output = r.stdout + r.stderr
        success = 'successfully authenticated' in output or 'Hi ' in output
        logger.info(f"SSH test {host} [{kp.name}]: {'OK' if success else 'FAIL'}")
        return {'success': success, 'output': output.strip(), 'host': host}
    except subprocess.TimeoutExpired:
        return {'success': False, 'output': f'Timeout : {host}', 'host': host}
    except Exception as e:
        return {'success': False, 'output': str(e), 'host': host}


def test_connection_for_remote(url: str, key_path: Optional[str] = None) -> dict:
    kp = key_path or str(_key_path('id_ed25519'))
    host = 'github.com'
    if '@' in url and ':' in url:
        try:
            host = url.split('@')[1].split(':')[0]
        except Exception:
            pass
    return test_connection_with_key(kp, host)


def _normalize_private_key(raw: str) -> Optional[str]:
    content = raw.replace('\\n', '\n').replace('\r\n', '\n').strip()
    if not content.startswith('-----BEGIN'):
        return None
    lines = content.split('\n')
    header, footer = lines[0].strip(), lines[-1].strip()
    body_lines = [l.strip() for l in lines[1:-1] if l.strip()]
    if len(body_lines) == 1 and len(body_lines[0]) > 64:
        b = body_lines[0]
        body_lines = [b[i:i+64] for i in range(0, len(b), 64)]
    return header + '\n' + '\n'.join(body_lines) + '\n' + footer + '\n'


def _rebuild_ssh_config():
    """Régénère ~/.ssh/config depuis toutes les clés présentes."""
    keys = list_all_keys()
    if not keys:
        return
    lines = []
    # Entrées generiques github/gitlab avec la première clé disponible
    default_key = keys[0]['key_path']
    lines.append(f"""Host github.com
  HostName github.com
  User git
  IdentityFile {default_key}
  IdentitiesOnly yes
  StrictHostKeyChecking no

Host gitlab.com
  HostName gitlab.com
  User git
  IdentityFile {default_key}
  IdentitiesOnly yes
  StrictHostKeyChecking no
""")
    config_path = SSH_DIR / 'config'
    config_path.write_text('\n'.join(lines))
    config_path.chmod(0o600)

def rename_key(old_name: str, new_name: str) -> dict:
    """Renomme les fichiers clé privée + publique."""
    old_priv = _key_path(old_name)
    old_pub = _pub_key_path(old_name)
    new_priv = _key_path(new_name)
    new_pub = _pub_key_path(new_name)

    if not old_priv.exists():
        return {'success': False, 'error': f'Clé "{old_name}" introuvable.'}
    if new_priv.exists():
        return {'success': False, 'error': f'Une clé "{new_name}" existe déjà.'}
    try:
        old_priv.rename(new_priv)
        if old_pub.exists():
            old_pub.rename(new_pub)
        _rebuild_ssh_config()
        logger.info(f"SSH key renamed: {old_name} → {new_name}")
        return {'success': True, 'new_key_path': str(new_priv)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
