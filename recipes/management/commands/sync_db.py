from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from recipes.models import MediaAsset, Recipe, RecipeBook, UserProfile


def _strip_media_fields(data: dict[str, Any]) -> dict[str, Any]:
    data = dict(data)

    for key in [
        'photo',
        'photo_url',
        'video',
        'video_url',
        'audio',
        'audio_url',
        'media',
        'media_url',
        'attachments',
        'files',
    ]:
        if key in data:
            data.pop(key, None)

    return data


class Command(BaseCommand):
    help = 'Bidirectional application-level sync between multiple DB aliases (default/peer*/cloud).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default='default',
            help='DB alias to read from (default/peer1/peer2/peer3/cloud).',
        )
        parser.add_argument(
            '--targets',
            default=None,
            help='Comma-separated target DB aliases. Default: all configured SYNC_DB_ALIASES except source.',
        )
        parser.add_argument(
            '--since-minutes',
            type=int,
            default=None,
            help='If provided, only sync records updated in last N minutes (best-effort).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do not write anything, just show what would be changed.',
        )

    def handle(self, *args, **options):
        source: str = options['source']
        targets_raw: str | None = options['targets']
        since_minutes: int | None = options['since_minutes']
        dry_run: bool = bool(options['dry_run'])

        aliases = getattr(settings, 'SYNC_DB_ALIASES', ['default'])
        if source not in aliases:
            raise SystemExit(f"Unknown source alias '{source}'. Available: {aliases}")

        if targets_raw:
            targets = [t.strip() for t in targets_raw.split(',') if t.strip()]
        else:
            targets = [a for a in aliases if a != source]

        targets = [t for t in targets if t in aliases]
        if not targets:
            self.stdout.write(self.style.WARNING('No targets to sync.'))
            return

        cutoff = None
        if since_minutes is not None:
            cutoff = timezone.now() - timezone.timedelta(minutes=since_minutes)

        # --------------- RECIPES ---------------
        qs = Recipe.objects.using(source).all().order_by('updated_at')
        if cutoff:
            qs = qs.filter(updated_at__gte=cutoff)

        source_recipes = list(qs)
        self.stdout.write(f'Syncing Recipe rows: {len(source_recipes)} from {source} -> {targets}')

        for target in targets:
            self._sync_recipes(source_recipes, source, target, dry_run)

        # --------------- MEDIA ASSETS ---------------
        asset_qs = MediaAsset.objects.using(source).all().order_by('updated_at')
        if cutoff:
            asset_qs = asset_qs.filter(updated_at__gte=cutoff)

        source_assets = list(asset_qs)
        self.stdout.write(f'Syncing MediaAsset rows: {len(source_assets)} from {source} -> {targets}')

        # Pre-build source recipe id→uuid map (needed for FK resolution)
        source_recipe_map = {r.id: r.uuid for r in source_recipes}

        for target in targets:
            self._sync_media_assets(source_assets, source, target, source_recipe_map, dry_run)

        # --------------- RECIPE BOOKS ---------------
        book_qs = RecipeBook.objects.using(source).all().order_by('updated_at')
        if cutoff:
            book_qs = book_qs.filter(updated_at__gte=cutoff)

        source_books = list(book_qs)
        self.stdout.write(f'Syncing RecipeBook rows: {len(source_books)} from {source} -> {targets}')

        for target in targets:
            self._sync_recipe_books(source_books, target, dry_run)

        # --------------- USER PROFILES ---------------
        profile_qs = UserProfile.objects.using(source).all().order_by('updated_at')
        if cutoff:
            profile_qs = profile_qs.filter(updated_at__gte=cutoff)

        source_profiles = list(profile_qs)
        self.stdout.write(f'Syncing UserProfile rows: {len(source_profiles)} from {source} -> {targets}')

        for target in targets:
            self._sync_user_profiles(source_profiles, target, dry_run)

    def _sync_recipes(self, source_rows: list[Recipe], source: str, target: str, dry_run: bool):
        """Batch-sync recipes to a single target using bulk operations."""
        is_cloud = target == 'cloud'

        # 1. Pre-fetch existing UUIDs + updated_at from target (single query)
        existing = {
            r.uuid: r
            for r in Recipe.objects.using(target).all().only('id', 'uuid', 'updated_at')
        }

        to_create = []
        to_update = []
        skipped = 0

        for r in source_rows:
            target_row = existing.get(r.uuid)
            data = _strip_media_fields(r.data) if is_cloud and isinstance(r.data, dict) else r.data

            if target_row:
                if target_row.updated_at and r.updated_at and target_row.updated_at >= r.updated_at:
                    skipped += 1
                    continue
                # Update existing
                target_row.data = data
                target_row.is_active = r.is_active
                target_row.is_public = r.is_public
                target_row.author_id = r.author_id
                target_row.updated_at = r.updated_at
                to_update.append(target_row)
            else:
                # Create new
                to_create.append(Recipe(
                    uuid=r.uuid,
                    data=data,
                    is_active=r.is_active,
                    is_public=r.is_public,
                    author_id=r.author_id,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        # 2. Bulk create new recipes (single INSERT with multiple VALUES)
        if to_create:
            Recipe.objects.using(target).bulk_create(to_create, batch_size=200)

        # 3. Bulk update changed recipes
        if to_update:
            Recipe.objects.using(target).bulk_update(
                to_update,
                fields=['data', 'is_active', 'is_public', 'author_id', 'updated_at'],
                batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done Recipe -> {target}: created={len(to_create)}, updated={len(to_update)}, skipped={skipped}'
        ))

    def _sync_media_assets(
        self,
        source_rows: list[MediaAsset],
        source: str,
        target: str,
        source_recipe_id_to_uuid: dict[int, str],
        dry_run: bool,
    ):
        """Batch-sync media assets to a single target using bulk operations."""
        is_cloud = target == 'cloud'

        # 1. Pre-fetch target recipe UUID→ID map (single query) for FK resolution
        target_recipe_uuid_to_id = {
            r.uuid: r.id
            for r in Recipe.objects.using(target).all().only('id', 'uuid')
        }

        # 2. Pre-fetch existing media asset UUIDs from target (single query)
        existing = {
            a.uuid: a
            for a in MediaAsset.objects.using(target).all().only('id', 'uuid', 'updated_at')
        }

        to_create = []
        to_update = []
        skipped = 0

        for a in source_rows:
            target_row = existing.get(a.uuid)

            # Resolve recipe FK via UUID
            target_recipe_id = None
            if a.recipe_id:
                recipe_uuid = source_recipe_id_to_uuid.get(a.recipe_id)
                if recipe_uuid:
                    target_recipe_id = target_recipe_uuid_to_id.get(recipe_uuid)

            local_path = None if is_cloud else a.local_path

            if target_row:
                if target_row.updated_at and a.updated_at and target_row.updated_at >= a.updated_at:
                    skipped += 1
                    continue
                target_row.kind = a.kind
                target_row.scope = a.scope
                target_row.url = a.url
                target_row.local_path = local_path
                target_row.size_bytes = a.size_bytes
                target_row.mime_type = a.mime_type
                target_row.checksum = a.checksum
                target_row.metadata = a.metadata
                target_row.owner_id = a.owner_id
                target_row.recipe_id = target_recipe_id
                target_row.profile_id = a.profile_id
                target_row.updated_at = a.updated_at
                to_update.append(target_row)
            else:
                to_create.append(MediaAsset(
                    uuid=a.uuid,
                    kind=a.kind,
                    scope=a.scope,
                    url=a.url,
                    local_path=local_path,
                    size_bytes=a.size_bytes,
                    mime_type=a.mime_type,
                    checksum=a.checksum,
                    metadata=a.metadata,
                    owner_id=a.owner_id,
                    recipe_id=target_recipe_id,
                    profile_id=a.profile_id,
                    created_at=a.created_at,
                    updated_at=a.updated_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN MediaAsset -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        if to_create:
            MediaAsset.objects.using(target).bulk_create(to_create, batch_size=200)

        if to_update:
            MediaAsset.objects.using(target).bulk_update(
                to_update,
                fields=['kind', 'scope', 'url', 'local_path', 'size_bytes', 'mime_type',
                        'checksum', 'metadata', 'owner_id', 'recipe_id', 'profile_id', 'updated_at'],
                batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done MediaAsset -> {target}: created={len(to_create)}, updated={len(to_update)}, skipped={skipped}'
        ))

    def _sync_recipe_books(self, source_rows: list[RecipeBook], target: str, dry_run: bool):
        """Batch-sync recipe books to a single target."""
        existing = {
            b.uuid: b
            for b in RecipeBook.objects.using(target).all().only('id', 'uuid', 'updated_at')
        }

        to_create = []
        to_update = []
        skipped = 0

        for b in source_rows:
            target_row = existing.get(b.uuid)
            if target_row:
                if target_row.updated_at and b.updated_at and target_row.updated_at >= b.updated_at:
                    skipped += 1
                    continue
                target_row.name = b.name
                target_row.data = b.data
                target_row.updated_at = b.updated_at
                to_update.append(target_row)
            else:
                to_create.append(RecipeBook(
                    uuid=b.uuid,
                    name=b.name,
                    data=b.data,
                    created_at=b.created_at,
                    updated_at=b.updated_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN RecipeBook -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        if to_create:
            RecipeBook.objects.using(target).bulk_create(to_create, batch_size=200)
        if to_update:
            RecipeBook.objects.using(target).bulk_update(
                to_update, fields=['name', 'data', 'updated_at'], batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done RecipeBook -> {target}: created={len(to_create)}, updated={len(to_update)}, skipped={skipped}'
        ))

    def _sync_user_profiles(self, source_rows: list[UserProfile], target: str, dry_run: bool):
        """Batch-sync user profiles to a single target.

        NOTE: We sync uuid + tasks JSON only.
        - user_id FK is NOT synced (auth.User ids differ across databases).
        - liked_recipes M2M is NOT synced here (handled by event-driven sync via outbox).
        """
        existing = {
            p.uuid: p
            for p in UserProfile.objects.using(target).all().only('id', 'uuid', 'updated_at')
        }

        to_create = []
        to_update = []
        skipped = 0

        for p in source_rows:
            target_row = existing.get(p.uuid)
            if target_row:
                if target_row.updated_at and p.updated_at and target_row.updated_at >= p.updated_at:
                    skipped += 1
                    continue
                target_row.tasks = p.tasks
                target_row.updated_at = p.updated_at
                to_update.append(target_row)
            else:
                to_create.append(UserProfile(
                    uuid=p.uuid,
                    user_id=p.user_id,  # Best-effort: may fail on cloud if user doesn't exist
                    tasks=p.tasks,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN UserProfile -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        if to_create:
            created_ok = 0
            for profile in to_create:
                try:
                    profile.save(using=target)
                    created_ok += 1
                except Exception as e:
                    self.stderr.write(f'  SKIP UserProfile uuid={profile.uuid}: {e}')
        else:
            created_ok = 0

        if to_update:
            UserProfile.objects.using(target).bulk_update(
                to_update, fields=['tasks', 'updated_at'], batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done UserProfile -> {target}: created={created_ok}, updated={len(to_update)}, skipped={skipped}'
        ))
