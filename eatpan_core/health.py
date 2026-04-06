import time
import io
import os
from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.core.management import call_command


def health(request):
    """
    Health check endpoint for Cloudflare Worker monitoring.
    Returns node identity and DB connectivity status.
    """
    node_id = getattr(settings, 'NODE_ID', 'unknown')
    start = time.monotonic()

    db_ok = False
    try:
        conn = connections['default']
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1')
        db_ok = True
    except Exception:
        pass

    elapsed_ms = round((time.monotonic() - start) * 1000, 1)

    status = 'ok' if db_ok else 'degraded'
    code = 200 if db_ok else 503

    return JsonResponse({
        'status': status,
        'node': node_id,
        'db': 'ok' if db_ok else 'error',
        'latency_ms': elapsed_ms,
    }, status=code)

