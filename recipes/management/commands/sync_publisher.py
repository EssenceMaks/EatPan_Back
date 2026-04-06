from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

import asyncio
from asgiref.sync import sync_to_async
from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig, RetentionPolicy
from nats.errors import TimeoutError as NatsTimeoutError

from recipes.models import SyncOutbox


@sync_to_async
def _fetch_pending(limit: int):
    """Fetch unpublished outbox events (runs in a thread-safe sync context)."""
    qs = (
        SyncOutbox.objects.filter(published_at__isnull=True)
        .order_by('created_at')
    )
    return list(qs[:limit])


@sync_to_async
def _mark_published(ev):
    ev.published_at = timezone.now()
    ev.last_error = None
    ev.save(update_fields=['published_at', 'last_error'])


@sync_to_async
def _mark_failed(ev, error_msg: str):
    ev.attempts = (ev.attempts or 0) + 1
    ev.last_error = error_msg
    ev.save(update_fields=['attempts', 'last_error'])


class Command(BaseCommand):
    help = 'Publish SyncOutbox events to NATS JetStream (sync broker).'

    def add_arguments(self, parser):
        parser.add_argument('--stream', default=None, help='JetStream stream name (defaults to settings.NATS_STREAM).')
        parser.add_argument('--subject', default=None, help='NATS subject (defaults to settings.NATS_SUBJECT).')
        parser.add_argument('--limit', type=int, default=200, help='Max events to publish per run.')
        parser.add_argument('--loop', action='store_true', help='Run continuously as a worker/daemon.')
        parser.add_argument('--sleep-seconds', type=float, default=0.5, help='Sleep between iterations in loop mode.')

    def handle(self, *args, **options):
        stream: str = options.get('stream') or getattr(settings, 'NATS_STREAM', 'eatpan_sync')
        subject: str = options.get('subject') or getattr(settings, 'NATS_SUBJECT', 'eatpan.sync')
        limit: int = int(options['limit'] or 0) or 200
        loop: bool = bool(options.get('loop'))
        sleep_seconds: float = float(options.get('sleep_seconds') or 0.5)

        asyncio.run(self._run(stream=stream, subject=subject, limit=limit, loop=loop, sleep_seconds=sleep_seconds))

    async def _ensure_stream(self, js, stream: str, subject: str) -> None:
        try:
            await js.stream_info(stream)
        except Exception:
            cfg = StreamConfig(name=stream, subjects=[subject], retention=RetentionPolicy.LIMITS)
            await js.add_stream(cfg)

    async def _run(self, *, stream: str, subject: str, limit: int, loop: bool, sleep_seconds: float) -> None:
        nc = NATS()
        await nc.connect(getattr(settings, 'NATS_URL', 'nats://nats:4222'))
        js = nc.jetstream()
        await self._ensure_stream(js, stream, subject)

        try:
            while True:
                events = await _fetch_pending(limit)

                if not events:
                    if not loop:
                        self.stdout.write('No outbox events to publish.')
                        return
                    await asyncio.sleep(sleep_seconds)
                    continue

                published = 0
                failed = 0

                for ev in events:
                    try:
                        msg = {
                            'outbox_id': ev.id,
                            'node_id': ev.node_id,
                            'entity_type': ev.entity_type,
                            'entity_uuid': str(ev.entity_uuid),
                            'op': ev.op,
                            'payload': ev.payload or {},
                            'created_at': ev.created_at.isoformat(),
                        }
                        data = json.dumps(msg, ensure_ascii=False).encode('utf-8')
                        await js.publish(subject, data)
                        await _mark_published(ev)
                        published += 1
                    except NatsTimeoutError as e:
                        await _mark_failed(ev, f"TimeoutError: {e}")
                        failed += 1
                    except Exception as e:
                        await _mark_failed(ev, f"{type(e).__name__}: {e}")
                        failed += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Published={published}, failed={failed}, stream={stream}, subject={subject}, node={getattr(settings, 'NODE_ID', '')}"
                    )
                )

                if not loop:
                    return

                await asyncio.sleep(sleep_seconds)
        finally:
            await nc.drain()
