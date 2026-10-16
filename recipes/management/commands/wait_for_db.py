from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = (
        'Wait until the default database accepts connections. '
        'Docker starts supabase-db and django_api at the same time after a reboot; '
        'without this runserver dies in check_migrations while the container stays "Up".'
    )

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=float, default=180, help='Give up after N seconds (exit 1, Docker restarts the container).')
        parser.add_argument('--interval', type=float, default=2, help='Seconds between attempts.')

    def handle(self, *args, **options):
        timeout: float = float(options['timeout'])
        interval: float = float(options['interval'])
        deadline = time.monotonic() + timeout
        conn = connections['default']
        attempt = 0

        while True:
            attempt += 1
            try:
                conn.ensure_connection()
                with conn.cursor() as cursor:
                    cursor.execute('SELECT 1')
            except OperationalError as e:
                conn.close()
                reason = (str(e).strip().splitlines() or [e.__class__.__name__])[0]
                if time.monotonic() >= deadline:
                    raise CommandError(f'Database still unavailable after {timeout:.0f}s: {reason}')
                self.stdout.write(f'Waiting for database (attempt {attempt}): {reason}')
                time.sleep(interval)
                continue

            conn.close()
            self.stdout.write(self.style.SUCCESS(f'Database is ready (attempt {attempt}).'))
            return
