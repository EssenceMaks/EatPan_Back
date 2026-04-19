from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.conf import settings

import asyncio
from asgiref.sync import sync_to_async
from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig, ConsumerConfig, AckPolicy, RetentionPolicy
from nats.errors import TimeoutError as NatsTimeoutError

from recipes.models import Recipe, RecipeBook, UserProfile


# ---------------------------------------------------------------------------
# Media-field stripping (cloud targets should not receive binary paths/URLs)
# ---------------------------------------------------------------------------
MEDIA_KEYS = frozenset([
    'photo', 'photo_url', 'video', 'video_url',
    'audio', 'audio_url', 'media', 'media_url',
    'attachments', 'files',
])

from recipes.models import (
    Recipe, RecipeBook, UserProfile,
    RecipeCategory, UserRecipeState, RecipeComment,
    RecipeReaction, CommentReaction
)


def _strip_media(data: dict) -> dict:
    """Return a shallow copy of *data* with media-related keys removed."""
    if not isinstance(data, dict):
        return data
    return {k: v for k, v in data.items() if k not in MEDIA_KEYS}


class Command(BaseCommand):
    help = 'Consume sync events from NATS JetStream and apply them to ALL target databases (local + cloud).'

    def add_arguments(self, parser):
        parser.add_argument('--stream', default=None, help='JetStream stream name (defaults to settings.NATS_STREAM).')
        parser.add_argument('--subject', default=None, help='NATS subject (defaults to settings.NATS_SUBJECT).')
        parser.add_argument('--durable', default=None, help='Durable consumer name (defaults to settings.NATS_DURABLE).')
        parser.add_argument('--batch', type=int, default=50, help='Batch size for pull consumer fetch.')
        parser.add_argument('--timeout-seconds', type=float, default=1.0, help='Fetch timeout (seconds).')
        parser.add_argument('--loop', action='store_true', help='Run continuously as a worker/daemon.')
        parser.add_argument('--sleep-seconds', type=float, default=0.5, help='Sleep between iterations in loop mode.')

    def handle(self, *args, **options):
        stream: str = options.get('stream') or getattr(settings, 'NATS_STREAM', 'eatpan_sync')
        subject: str = options.get('subject') or getattr(settings, 'NATS_SUBJECT', 'eatpan.sync')
        durable: str = options.get('durable') or getattr(settings, 'NATS_DURABLE', 'eatpan_sync_worker')
        batch: int = int(options.get('batch') or 50)
        timeout_seconds: float = float(options.get('timeout_seconds') or 1.0)
        loop: bool = bool(options.get('loop'))
        sleep_seconds: float = float(options.get('sleep_seconds') or 0.5)

        asyncio.run(self._run(stream=stream, subject=subject, durable=durable, batch=batch, timeout_seconds=timeout_seconds, loop=loop, sleep_seconds=sleep_seconds))

    async def _ensure_stream(self, js, stream: str, subject: str) -> None:
        try:
            await js.stream_info(stream)
        except Exception:
            cfg = StreamConfig(name=stream, subjects=[subject], retention=RetentionPolicy.LIMITS)
            await js.add_stream(cfg)

    async def _ensure_consumer(self, js, stream: str, durable: str) -> None:
        try:
            await js.consumer_info(stream, durable)
        except Exception:
            cfg = ConsumerConfig(durable_name=durable, ack_policy=AckPolicy.EXPLICIT)
            await js.add_consumer(stream, cfg)

    async def _run(self, *, stream: str, subject: str, durable: str, batch: int, timeout_seconds: float, loop: bool, sleep_seconds: float) -> None:
        nc = NATS()
        await nc.connect(getattr(settings, 'NATS_URL', 'nats://nats:4222'))
        js = nc.jetstream()
        await self._ensure_stream(js, stream, subject)
        await self._ensure_consumer(js, stream, durable)

        sub = await js.pull_subscribe(subject, durable=durable, stream=stream)

        # Determine target DB aliases — all configured aliases (including cloud)
        all_aliases = getattr(settings, 'SYNC_DB_ALIASES', ['default'])
        targets = [a for a in all_aliases if a != 'default']
        # Always include 'default' as a target too
        targets = ['default'] + targets
        self.stdout.write(f'Sync targets: {targets}')

        try:
            while True:
                applied = 0
                try:
                    msgs = await sub.fetch(batch, timeout=timeout_seconds)
                except NatsTimeoutError:
                    msgs = []

                if not msgs:
                    if not loop:
                        self.stdout.write('No events.')
                        return
                    await asyncio.sleep(sleep_seconds)
                    continue

                for msg in msgs:
                    try:
                        data = json.loads(msg.data.decode('utf-8'))
                        entity_type = str(data.get('entity_type') or '')
                        op = str(data.get('op') or '')
                        entity_uuid = str(data.get('entity_uuid') or '')
                        payload = data.get('payload') or {}

                        # Apply to ALL targets (default + cloud + peers)
                        for db_alias in targets:
                            is_cloud = db_alias == 'cloud'
                            try:
                                if entity_type == 'recipe':
                                    await _apply_recipe(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias, strip_media=is_cloud)
                                elif entity_type == 'recipe_book':
                                    await _apply_recipe_book(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                                elif entity_type == 'user_profile':
                                    await _apply_user_profile(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                                elif entity_type == 'recipe_category':
                                    await _apply_recipe_category(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                                elif entity_type == 'user_recipe_state':
                                    await _apply_user_recipe_state(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                                elif entity_type == 'recipe_comment':
                                    await _apply_recipe_comment(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                                elif entity_type == 'recipe_reaction':
                                    await _apply_recipe_reaction(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                                elif entity_type == 'comment_reaction':
                                    await _apply_comment_reaction(op=op, entity_uuid=entity_uuid, payload=payload, db_alias=db_alias)
                            except Exception as e:
                                # Log but don't block other targets
                                self.stderr.write(f'  WARN apply {entity_type} to {db_alias}: {e}')

                        await msg.ack()
                        applied += 1
                    except Exception:
                        # Don't ack on failure to allow redelivery
                        continue

                self.stdout.write(self.style.SUCCESS(f'Applied={applied}, targets={targets}, durable={durable}, stream={stream}'))

                if not loop:
                    return
        finally:
            await nc.drain()


@sync_to_async
def _apply_recipe(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default', strip_media: bool = False) -> None:
    if op == 'delete':
        Recipe.objects.using(db_alias).filter(uuid=entity_uuid).update(is_active=False)
        return

    data = payload.get('data')
    if not isinstance(data, dict):
        return

    # Strip media fields when syncing to cloud (media stays local only)
    if strip_media:
        data = _strip_media(data)

    defaults = {
        'data': data,
        'is_active': bool(payload.get('is_active', True)),
        'is_public': bool(payload.get('is_public', True)),
    }

    Recipe.objects.using(db_alias).update_or_create(uuid=entity_uuid, defaults=defaults)


@sync_to_async
def _apply_user_profile(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    if op not in ('upsert', 'patch'):
        return

    # Patch tasks if provided
    if 'tasks' in payload:
        tasks = payload.get('tasks')
        if tasks is not None:
            UserProfile.objects.using(db_alias).filter(uuid=entity_uuid).update(tasks=tasks)

    # Patch liked recipes if provided (UUID-based)
    if 'liked_recipe_uuids' in payload:
        raw = payload.get('liked_recipe_uuids')
        if isinstance(raw, list):
            uuids = [u for u in raw if isinstance(u, str) and u]
            try:
                profile = UserProfile.objects.using(db_alias).filter(uuid=entity_uuid).first()
                if not profile:
                    return
                liked = Recipe.objects.using(db_alias).filter(uuid__in=uuids).only('id')
                profile.liked_recipes.set(liked)
            except Exception:
                return


@sync_to_async
def _apply_recipe_book(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    if op == 'delete':
        RecipeBook.objects.using(db_alias).filter(uuid=entity_uuid).delete()
        return

    name = payload.get('name')
    data = payload.get('data')
    if not isinstance(name, str) or not name:
        return
    if data is not None and not isinstance(data, dict):
        return

    defaults = {
        'name': name,
        'data': data or {},
    }
    RecipeBook.objects.using(db_alias).update_or_create(uuid=entity_uuid, defaults=defaults)


@sync_to_async
def _apply_recipe_category(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    if op == 'delete':
        RecipeCategory.objects.using(db_alias).filter(uuid=entity_uuid).delete()
        return
    data = payload.get('data')
    if not isinstance(data, dict):
        return
    defaults = {
        'data': data
    }
    RecipeCategory.objects.using(db_alias).update_or_create(uuid=entity_uuid, defaults=defaults)


@sync_to_async
def _apply_user_recipe_state(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    if op == 'delete':
        UserRecipeState.objects.using(db_alias).filter(uuid=entity_uuid).delete()
        return

    recipe_uuid = payload.get('recipe_uuid')
    user_id = payload.get('user_id')

    if not recipe_uuid or not user_id:
        return

    recipe = Recipe.objects.using(db_alias).filter(uuid=recipe_uuid).only('id').first()
    if not recipe:
        return

    defaults = {
        'user_id': user_id,
        'recipe_id': recipe.id,
        'is_planned': bool(payload.get('is_planned')),
        'is_cooked': bool(payload.get('is_cooked')),
        'cooked_date': payload.get('cooked_date'),
        'expiration_date': payload.get('expiration_date'),
        'location': payload.get('location', ''),
        'cook_count': int(payload.get('cook_count', 0)),
        'personal_digestion_time': payload.get('personal_digestion_time', ''),
    }
    UserRecipeState.objects.using(db_alias).update_or_create(uuid=entity_uuid, defaults=defaults)


@sync_to_async
def _apply_recipe_comment(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    if op == 'delete':
        RecipeComment.objects.using(db_alias).filter(uuid=entity_uuid).delete()
        return

    recipe_uuid = payload.get('recipe_uuid')
    author_id = payload.get('author_id')
    text = payload.get('text')

    if not recipe_uuid or not author_id or not text:
        return

    recipe = Recipe.objects.using(db_alias).filter(uuid=recipe_uuid).only('id').first()
    if not recipe:
        return

    defaults = {
        'recipe_id': recipe.id,
        'author_id': author_id,
        'text': text,
    }
    RecipeComment.objects.using(db_alias).update_or_create(uuid=entity_uuid, defaults=defaults)


@sync_to_async
def _apply_recipe_reaction(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    recipe_uuid = payload.get('recipe_uuid')
    user_id = payload.get('user_id')
    emoji_type = payload.get('emoji_type')

    if not recipe_uuid or not user_id or not emoji_type:
        return

    recipe = Recipe.objects.using(db_alias).filter(uuid=recipe_uuid).only('id').first()
    if not recipe:
        return

    if op == 'delete':
        RecipeReaction.objects.using(db_alias).filter(recipe_id=recipe.id, user_id=user_id, emoji_type=emoji_type).delete()
        return

    # Reactions don't have UUIDs, so we use update_or_create by their unique together fields
    defaults = {
        'recipe_id': recipe.id,
        'user_id': user_id,
        'emoji_type': emoji_type,
    }
    RecipeReaction.objects.using(db_alias).get_or_create(recipe_id=recipe.id, user_id=user_id, emoji_type=emoji_type, defaults=defaults)


@sync_to_async
def _apply_comment_reaction(*, op: str, entity_uuid: str, payload: dict, db_alias: str = 'default') -> None:
    comment_uuid = payload.get('comment_uuid')
    user_id = payload.get('user_id')
    emoji_type = payload.get('emoji_type')

    if not comment_uuid or not user_id or not emoji_type:
        return

    comment = RecipeComment.objects.using(db_alias).filter(uuid=comment_uuid).only('id').first()
    if not comment:
        return

    if op == 'delete':
        CommentReaction.objects.using(db_alias).filter(comment_id=comment.id, user_id=user_id, emoji_type=emoji_type).delete()
        return

    defaults = {
        'comment_id': comment.id,
        'user_id': user_id,
        'emoji_type': emoji_type,
    }
    CommentReaction.objects.using(db_alias).get_or_create(comment_id=comment.id, user_id=user_id, emoji_type=emoji_type, defaults=defaults)
