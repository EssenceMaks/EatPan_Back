from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from recipes.models import (
    MediaAsset, Recipe, RecipeBook, UserProfile,
    RecipeCategory, UserRecipeState, RecipeComment,
    RecipeReaction, CommentReaction
)

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

        # --------------- RECIPE CATEGORIES ---------------
        cat_qs = RecipeCategory.objects.using(source).all().order_by('created_at')
        source_cats = list(cat_qs)
        self.stdout.write(f'Syncing RecipeCategory rows: {len(source_cats)} from {source} -> {targets}')

        for target in targets:
            self._sync_recipe_categories(source_cats, target, dry_run)

        # --------------- USER RECIPE STATES ---------------
        state_qs = UserRecipeState.objects.using(source).all().order_by('updated_at')
        if cutoff:
            state_qs = state_qs.filter(updated_at__gte=cutoff)
        source_states = list(state_qs)
        self.stdout.write(f'Syncing UserRecipeState rows: {len(source_states)} from {source} -> {targets}')

        for target in targets:
            self._sync_user_recipe_states(source_states, target, source_recipe_map, dry_run)

        # --------------- RECIPE COMMENTS ---------------
        comment_qs = RecipeComment.objects.using(source).all().order_by('updated_at')
        if cutoff:
            comment_qs = comment_qs.filter(updated_at__gte=cutoff)
        source_comments = list(comment_qs)
        self.stdout.write(f'Syncing RecipeComment rows: {len(source_comments)} from {source} -> {targets}')

        for target in targets:
            self._sync_recipe_comments(source_comments, target, source_recipe_map, dry_run)

        # --------------- RECIPE REACTIONS ---------------
        r_react_qs = RecipeReaction.objects.using(source).all().order_by('created_at')
        source_r_reacts = list(r_react_qs)
        self.stdout.write(f'Syncing RecipeReaction rows: {len(source_r_reacts)} from {source} -> {targets}')

        for target in targets:
            self._sync_recipe_reactions(source_r_reacts, target, source_recipe_map, dry_run)

        # --------------- COMMENT REACTIONS ---------------
        c_react_qs = CommentReaction.objects.using(source).all().order_by('created_at')
        source_c_reacts = list(c_react_qs)
        
        # Need source comment map for comment reactions
        source_comment_map = {c.id: c.uuid for c in source_comments}
        
        self.stdout.write(f'Syncing CommentReaction rows: {len(source_c_reacts)} from {source} -> {targets}')

        for target in targets:
            self._sync_comment_reactions(source_c_reacts, target, source_comment_map, dry_run)

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

    def _sync_recipe_categories(self, source_rows: list[RecipeCategory], target: str, dry_run: bool):
        existing = {
            c.uuid: c
            for c in RecipeCategory.objects.using(target).all().only('id', 'uuid')
        }
        to_create = []
        to_update = []
        skipped = 0

        for c in source_rows:
            target_row = existing.get(c.uuid)
            if target_row:
                # categories don't have updated_at, so we just check created_at or skip check and update
                target_row.data = c.data
                to_update.append(target_row)
            else:
                to_create.append(RecipeCategory(
                    uuid=c.uuid,
                    data=c.data,
                    created_at=c.created_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN RecipeCategory -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        if to_create:
            RecipeCategory.objects.using(target).bulk_create(to_create, batch_size=200)
        
        if to_update:
            RecipeCategory.objects.using(target).bulk_update(
                to_update, fields=['data'], batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done RecipeCategory -> {target}: created={len(to_create)}, updated={len(to_update)}, skipped={skipped}'
        ))

    def _sync_user_recipe_states(self, source_rows: list[UserRecipeState], target: str, source_recipe_id_to_uuid: dict[int, str], dry_run: bool):
        target_recipe_uuid_to_id = {
            r.uuid: r.id
            for r in Recipe.objects.using(target).all().only('id', 'uuid')
        }
        existing = {
            s.uuid: s
            for s in UserRecipeState.objects.using(target).all().only('id', 'uuid', 'updated_at')
        }
        to_create = []
        to_update = []
        skipped = 0

        for s in source_rows:
            target_row = existing.get(s.uuid)
            
            target_recipe_id = None
            if s.recipe_id:
                recipe_uuid = source_recipe_id_to_uuid.get(s.recipe_id)
                if recipe_uuid:
                    target_recipe_id = target_recipe_uuid_to_id.get(recipe_uuid)

            if target_row:
                if target_row.updated_at and s.updated_at and target_row.updated_at >= s.updated_at:
                    skipped += 1
                    continue
                target_row.is_planned = s.is_planned
                target_row.is_cooked = s.is_cooked
                target_row.cooked_date = s.cooked_date
                target_row.expiration_date = s.expiration_date
                target_row.location = s.location
                target_row.cook_count = s.cook_count
                target_row.personal_digestion_time = s.personal_digestion_time
                target_row.updated_at = s.updated_at
                to_update.append(target_row)
            else:
                to_create.append(UserRecipeState(
                    uuid=s.uuid,
                    user_id=s.user_id,
                    recipe_id=target_recipe_id,
                    is_planned=s.is_planned,
                    is_cooked=s.is_cooked,
                    cooked_date=s.cooked_date,
                    expiration_date=s.expiration_date,
                    location=s.location,
                    cook_count=s.cook_count,
                    personal_digestion_time=s.personal_digestion_time,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN UserRecipeState -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        if to_create:
            created_ok = 0
            for state in to_create:
                try:
                    state.save(using=target)
                    created_ok += 1
                except Exception as e:
                    self.stderr.write(f'  SKIP UserRecipeState uuid={state.uuid}: {e}')
        else:
            created_ok = 0

        if to_update:
            UserRecipeState.objects.using(target).bulk_update(
                to_update, fields=['is_planned', 'is_cooked', 'cooked_date', 'expiration_date', 'location', 'cook_count', 'personal_digestion_time', 'updated_at'], batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done UserRecipeState -> {target}: created={created_ok}, updated={len(to_update)}, skipped={skipped}'
        ))

    def _sync_recipe_comments(self, source_rows: list[RecipeComment], target: str, source_recipe_id_to_uuid: dict[int, str], dry_run: bool):
        target_recipe_uuid_to_id = {
            r.uuid: r.id
            for r in Recipe.objects.using(target).all().only('id', 'uuid')
        }
        existing = {
            c.uuid: c
            for c in RecipeComment.objects.using(target).all().only('id', 'uuid', 'updated_at')
        }
        to_create = []
        to_update = []
        skipped = 0

        for c in source_rows:
            target_row = existing.get(c.uuid)
            
            target_recipe_id = None
            if c.recipe_id:
                recipe_uuid = source_recipe_id_to_uuid.get(c.recipe_id)
                if recipe_uuid:
                    target_recipe_id = target_recipe_uuid_to_id.get(recipe_uuid)

            if target_row:
                if target_row.updated_at and c.updated_at and target_row.updated_at >= c.updated_at:
                    skipped += 1
                    continue
                target_row.text = c.text
                target_row.updated_at = c.updated_at
                to_update.append(target_row)
            else:
                to_create.append(RecipeComment(
                    uuid=c.uuid,
                    recipe_id=target_recipe_id,
                    author_id=c.user_id if hasattr(c, 'user_id') else c.author_id,
                    text=c.text,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN RecipeComment -> {target}: would create={len(to_create)}, update={len(to_update)}, skip={skipped}')
            return

        if to_create:
            created_ok = 0
            for comment in to_create:
                try:
                    comment.save(using=target)
                    created_ok += 1
                except Exception as e:
                    self.stderr.write(f'  SKIP RecipeComment uuid={comment.uuid}: {e}')
        else:
            created_ok = 0

        if to_update:
            RecipeComment.objects.using(target).bulk_update(
                to_update, fields=['text', 'updated_at'], batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  Done RecipeComment -> {target}: created={created_ok}, updated={len(to_update)}, skipped={skipped}'
        ))

    def _sync_recipe_reactions(self, source_rows: list[RecipeReaction], target: str, source_recipe_id_to_uuid: dict[int, str], dry_run: bool):
        target_recipe_uuid_to_id = {
            r.uuid: r.id
            for r in Recipe.objects.using(target).all().only('id', 'uuid')
        }
        existing = set(
            RecipeReaction.objects.using(target).values_list('recipe_id', 'user_id', 'emoji_type')
        )
        to_create = []
        skipped = 0

        for r in source_rows:
            target_recipe_id = None
            if r.recipe_id:
                recipe_uuid = source_recipe_id_to_uuid.get(r.recipe_id)
                if recipe_uuid:
                    target_recipe_id = target_recipe_uuid_to_id.get(recipe_uuid)
            
            key = (target_recipe_id, r.user_id, r.emoji_type)
            if key in existing or not target_recipe_id:
                skipped += 1
                continue
            
            to_create.append(RecipeReaction(
                recipe_id=target_recipe_id,
                user_id=r.user_id,
                emoji_type=r.emoji_type,
                created_at=r.created_at,
            ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN RecipeReaction -> {target}: would create={len(to_create)}, skip={skipped}')
            return

        if to_create:
            created_ok = 0
            for reaction in to_create:
                try:
                    reaction.save(using=target)
                    created_ok += 1
                except Exception as e:
                    pass
        else:
            created_ok = 0

        self.stdout.write(self.style.SUCCESS(
            f'  Done RecipeReaction -> {target}: created={created_ok}, skipped={skipped}'
        ))

    def _sync_comment_reactions(self, source_rows: list[CommentReaction], target: str, source_comment_id_to_uuid: dict[int, str], dry_run: bool):
        target_comment_uuid_to_id = {
            c.uuid: c.id
            for c in RecipeComment.objects.using(target).all().only('id', 'uuid')
        }
        existing = set(
            CommentReaction.objects.using(target).values_list('comment_id', 'user_id', 'emoji_type')
        )
        to_create = []
        skipped = 0

        for r in source_rows:
            target_comment_id = None
            if r.comment_id:
                comment_uuid = source_comment_id_to_uuid.get(r.comment_id)
                if comment_uuid:
                    target_comment_id = target_comment_uuid_to_id.get(comment_uuid)
            
            key = (target_comment_id, r.user_id, r.emoji_type)
            if key in existing or not target_comment_id:
                skipped += 1
                continue
            
            to_create.append(CommentReaction(
                comment_id=target_comment_id,
                user_id=r.user_id,
                emoji_type=r.emoji_type,
                created_at=r.created_at,
            ))

        if dry_run:
            self.stdout.write(f'  DRY_RUN CommentReaction -> {target}: would create={len(to_create)}, skip={skipped}')
            return

        if to_create:
            created_ok = 0
            for reaction in to_create:
                try:
                    reaction.save(using=target)
                    created_ok += 1
                except Exception as e:
                    pass
        else:
            created_ok = 0

        self.stdout.write(self.style.SUCCESS(
            f'  Done CommentReaction -> {target}: created={created_ok}, skipped={skipped}'
        ))
