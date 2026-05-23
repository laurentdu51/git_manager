import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger('git_manager')


def send_slack_alert(alerts):
    webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
    if not webhook_url:
        return

    color_map = {
        'ahead': '#4ade80',
        'behind': '#fb923c',
        'diverged': '#f87171',
        'error': '#f87171',
    }

    blocks = [
        {
            'type': 'header',
            'text': {'type': 'plain_text', 'text': f'⚠️ {len(alerts)} remote(s) nécessitent attention'}
        },
        {'type': 'divider'},
    ]

    for a in alerts[:10]:
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': (
                    f'*{a["repo"]}* → `{a["remote"]}` ({a["branch"]})\n'
                    f'Status: *{a["status"]}*  ·  ↑{a["ahead"]}  ↓{a["behind"]}'
                ),
            },
        })

    if len(alerts) > 10:
        blocks.append({
            'type': 'context',
            'elements': [{'type': 'mrkdwn', 'text': f'… et {len(alerts) - 10} autre(s)'}],
        })

    payload = json.dumps({'blocks': blocks}).encode('utf-8')
    req = Request(webhook_url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        urlopen(req, timeout=10)
        logger.info(f'Notification Slack envoyée: {len(alerts)} alertes')
    except URLError as e:
        logger.error(f'Erreur envoi Slack: {e}')


EMAIL_SUBJECT = '[Git Manager] Alerte remote'


def send_email_alert(alerts):
    recipient = getattr(settings, 'ALERT_EMAIL_TO', None)
    if not recipient:
        return

    lines = [f'{len(alerts)} remote(s) nécessitent attention:\n']
    for a in alerts:
        lines.append(f'  - {a["repo"]}/{a["remote"]} ({a["branch"]}): {a["status"]} (↑{a["ahead"]} ↓{a["behind"]})')

    message = '\n'.join(lines)

    try:
        send_mail(
            subject=EMAIL_SUBJECT,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info(f'Email d\'alerte envoyé à {recipient}: {len(alerts)} alertes')
    except Exception as e:
        logger.error(f'Erreur envoi email: {e}')


def send_alerts(alerts):
    if not alerts:
        return
    send_slack_alert(alerts)
    send_email_alert(alerts)
