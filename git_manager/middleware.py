from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from functools import wraps
import time


def api_auth_required(view_func):
    """Decorator that checks Bearer token in Authorization header."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        token = getattr(settings, 'API_TOKEN', None)
        if not token:
            return view_func(request, *args, **kwargs)

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != token:
            return JsonResponse({'error': 'Authentification requise'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped


def rate_limit(requests_per_minute=60, key_prefix='rate_limit'):
    """Decorator for rate limiting API endpoints."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown'))
            ip = ip.split(',')[0].strip() if ',' in ip else ip

            cache_key = f'{key_prefix}_{ip}'
            now = time.time()

            request_data = cache.get(cache_key)
            if request_data is None:
                request_data = {'count': 0, 'start_time': now}

            elapsed = now - request_data['start_time']
            if elapsed > 60:
                request_data = {'count': 0, 'start_time': now}

            request_data['count'] += 1
            cache.set(cache_key, request_data, 65)

            if request_data['count'] > requests_per_minute:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'retry_after': int(60 - elapsed)
                }, status=429)

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator