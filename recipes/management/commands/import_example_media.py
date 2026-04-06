from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.error
import urllib.request
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from recipes.models import MediaAsset, Recipe


_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@dataclass(frozen=True)
class FoundMedia:
    url: str
    kind: str
    source_path: str


def _guess_kind_from_url(url: str) -> str:
    u = url.lower()
    if any(u.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.svg']):
        return MediaAsset.KIND_IMAGE
    if any(u.endswith(ext) for ext in ['.mp4', '.mov', '.mkv', '.webm']):
        return MediaAsset.KIND_VIDEO
    if any(u.endswith(ext) for ext in ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac']):
        return MediaAsset.KIND_AUDIO
    return MediaAsset.KIND_FILE


def _safe_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    name = os.path.basename(parsed.path)
    if not name:
        name = 'asset'
    name = urllib.parse.unquote(name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:255]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, timeout_seconds: int = 30) -> tuple[int | None, str | None]:
    dest.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'EatPanImporter/1.0',
            'Accept': '*/*',
        },
        method='GET',
    )

    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data = resp.read()
                dest.write_bytes(data)
                content_type = resp.headers.get('Content-Type')
                return len(data), content_type
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise
            last_exc = e
        except urllib.error.URLError as e:
            last_exc = e

        if attempt < 3:
            time.sleep(1.5 * (2 ** attempt))

    assert last_exc is not None
    raise last_exc


def _supabase_upload_file(
    *,
    supabase_url: str,
    service_role_key: str,
    bucket: str,
    object_path: str,
    file_path: Path,
    content_type: str | None,
) -> None:
    base = supabase_url.rstrip('/')
    url = f"{base}/storage/v1/object/{bucket}/{object_path.lstrip('/')}"

    headers = {
        'Authorization': f'Bearer {service_role_key}',
        'apikey': service_role_key,
        'x-upsert': 'true',
    }
    if content_type:
        headers['Content-Type'] = content_type

    data = file_path.read_bytes()
    req = urllib.request.Request(url, data=data, headers=headers, method='PUT')
    with urllib.request.urlopen(req, timeout=60) as resp:
        _ = resp.read()


def _extract_media_urls(obj: Any, *, path: str = '$') -> Iterable[FoundMedia]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}"
            if isinstance(v, str) and _URL_RE.match(v):
                kind = _guess_kind_from_url(v)
                yield FoundMedia(url=v, kind=kind, source_path=new_path)
            else:
                yield from _extract_media_urls(v, path=new_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from _extract_media_urls(item, path=f"{path}[{i}]")


def _resolve_input_path(raw_path: str) -> Path:
    p = Path(raw_path)
    if p.is_absolute() and p.exists():
        return p

    candidates: list[Path] = []
    candidates.append(Path.cwd() / raw_path)
    candidates.append(Path('/app') / raw_path)
    candidates.append(Path('/workspace') / raw_path)

    for c in candidates:
        if c.exists():
            return c

    checked = "\n".join(str(c) for c in candidates)
    raise FileNotFoundError(f"Input file not found: {raw_path}. Checked:\n{checked}")


class Command(BaseCommand):
    help = 'Import media referenced by example_data JSON into Supabase Storage (study tag) and create MediaAsset rows.'

    def add_arguments(self, parser):
        parser.add_argument('--recipes-json', default='example_data/recipes.json')
        parser.add_argument('--include-ingredients', action='store_true', default=False)
        parser.add_argument('--ingredients-json', default='example_data/ingredients.json')
        parser.add_argument('--tag', default='study')
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--print-errors', action='store_true', default=False)
        parser.add_argument('--error-limit', type=int, default=20)
        parser.add_argument('--to-supabase-storage', action='store_true', default=False)
        parser.add_argument('--supabase-url', default=os.environ.get('SUPABASE_URL') or '')
        parser.add_argument('--supabase-service-role-key', default=os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or '')
        parser.add_argument('--bucket', default=os.environ.get('SUPABASE_MEDIA_BUCKET') or 'ideatpanmedia')

    def handle(self, *args, **options):
        recipes_json = options['recipes_json']
        include_ingredients = options['include_ingredients']
        ingredients_json = options['ingredients_json']
        tag = options['tag']
        limit = options['limit']
        dry_run = options['dry_run']
        print_errors = bool(options.get('print_errors'))
        error_limit = int(options.get('error_limit') or 0)
        to_supabase_storage = options['to_supabase_storage']
        supabase_url = (options['supabase_url'] or '').strip()
        service_role_key = (options['supabase_service_role_key'] or '').strip()
        bucket_name = (options['bucket'] or 'ideatpanmedia').strip()
        supabase_public_url = (os.environ.get('SUPABASE_PUBLIC_URL') or supabase_url).strip()

        if not to_supabase_storage and supabase_url and service_role_key:
            to_supabase_storage = True

        if to_supabase_storage and (not supabase_url or not service_role_key):
            raise RuntimeError('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set (or provided via args)')

        recipes_path = _resolve_input_path(recipes_json)
        with open(recipes_path, 'r', encoding='utf-8') as f:
            recipes_raw = json.load(f)

        if limit is not None:
            recipes_raw = recipes_raw[:limit]

        created_assets = 0
        reused_assets = 0
        downloaded = 0
        failed = 0
        skipped_missing = 0
        printed_errors = 0

        for idx, raw in enumerate(recipes_raw):
            r_id = raw.get('_id', {})
            if isinstance(r_id, dict) and '$oid' in r_id:
                r_id = r_id['$oid']

            parsed_id = f"GLOBAL_PARSE_RECIPE_{r_id}" if r_id else None
            if not parsed_id:
                continue

            recipe = Recipe.objects.filter(data__parsed_id=parsed_id).first()
            if not recipe:
                continue

            found = list(_extract_media_urls(raw))
            if not found:
                continue

            media_bucket_map: dict[str, list[str]] = {
                'images': [],
                'videos': [],
                'audios': [],
                'files': [],
            }

            for item in found:
                url = item.url
                kind = item.kind

                filename = _safe_filename_from_url(url)
                object_path = f"{tag}/recipes/{recipe.uuid}/{filename}"

                if dry_run:
                    self.stdout.write(f"DRY_RUN download {url} -> {object_path}")
                    continue

                size_bytes: int | None = None
                mime_type: str | None = None
                checksum: str | None = None
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        tmp_path = Path(tmp_dir) / filename
                        size_bytes, mime_type = _download(url, tmp_path)
                        try:
                            checksum = _sha256_file(tmp_path)
                        except Exception:
                            checksum = None
                        if to_supabase_storage:
                            _supabase_upload_file(
                                supabase_url=supabase_url,
                                service_role_key=service_role_key,
                                bucket=bucket_name,
                                object_path=object_path,
                                file_path=tmp_path,
                                content_type=mime_type,
                            )
                        downloaded += 1
                except Exception as e:
                    if isinstance(e, urllib.error.HTTPError) and e.code in (404, 410):
                        skipped_missing += 1
                        continue

                    failed += 1
                    if print_errors and (error_limit <= 0 or printed_errors < error_limit):
                        self.stderr.write(
                            f"ERROR recipe_media url={url} object_path={object_path} exc={type(e).__name__}: {e}"
                        )
                        printed_errors += 1
                    continue

                public_url = None
                if to_supabase_storage:
                    public_url = f"{supabase_public_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{object_path}"

                with transaction.atomic():
                    existing = None
                    if checksum:
                        existing = MediaAsset.objects.filter(checksum=checksum, recipe=recipe).first()
                    if not existing:
                        existing = MediaAsset.objects.filter(url=url, recipe=recipe).first()

                    if existing:
                        asset = existing
                        reused_assets += 1
                    else:
                        asset = MediaAsset.objects.create(
                            kind=kind,
                            scope=MediaAsset.SCOPE_LOCAL_ONLY,
                            url=public_url or url,
                            local_path=None,
                            size_bytes=size_bytes,
                            mime_type=mime_type,
                            checksum=checksum,
                            metadata={
                                'tag': tag,
                                'source': 'example_data',
                                'source_path': item.source_path,
                                'note': 'study',
                                'storage_bucket': bucket_name,
                                'storage_path': object_path,
                            },
                            recipe=recipe,
                            owner=recipe.author,
                        )
                        created_assets += 1

                u = str(asset.uuid)
                if kind == MediaAsset.KIND_IMAGE:
                    if u not in media_bucket_map['images']:
                        media_bucket_map['images'].append(u)
                elif kind == MediaAsset.KIND_VIDEO:
                    if u not in media_bucket_map['videos']:
                        media_bucket_map['videos'].append(u)
                elif kind == MediaAsset.KIND_AUDIO:
                    if u not in media_bucket_map['audios']:
                        media_bucket_map['audios'].append(u)
                else:
                    if u not in media_bucket_map['files']:
                        media_bucket_map['files'].append(u)

            if dry_run:
                continue

            if any(media_bucket_map.values()):
                data = dict(recipe.data or {})
                media = dict(data.get('media') or {})

                for k in ['images', 'videos', 'audios', 'files']:
                    existing_list = list(media.get(k) or [])
                    for u in media_bucket_map[k]:
                        if u not in existing_list:
                            existing_list.append(u)
                    if existing_list:
                        media[k] = existing_list
                data['media'] = media

                Recipe.objects.filter(pk=recipe.pk).update(data=data)

        if include_ingredients:
            ingredients_path = _resolve_input_path(ingredients_json)
            with open(ingredients_path, 'r', encoding='utf-8') as f:
                ingredients_raw = json.load(f)

            for ing in ingredients_raw:
                ing_id = ing.get('_id', {})
                if isinstance(ing_id, dict) and '$oid' in ing_id:
                    ing_id = ing_id['$oid']
                if not ing_id:
                    continue

                url = ing.get('img')
                if not isinstance(url, str) or not _URL_RE.match(url):
                    continue

                filename = _safe_filename_from_url(url)
                object_path = f"{tag}/ingredients/{ing_id}/{filename}"

                if dry_run:
                    self.stdout.write(f"DRY_RUN download ingredient {ing_id} {url} -> {object_path}")
                    continue

                size_bytes: int | None = None
                mime_type: str | None = None
                checksum: str | None = None
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        tmp_path = Path(tmp_dir) / filename
                        size_bytes, mime_type = _download(url, tmp_path)
                        try:
                            checksum = _sha256_file(tmp_path)
                        except Exception:
                            checksum = None
                        if to_supabase_storage:
                            _supabase_upload_file(
                                supabase_url=supabase_url,
                                service_role_key=service_role_key,
                                bucket=bucket_name,
                                object_path=object_path,
                                file_path=tmp_path,
                                content_type=mime_type,
                            )
                        downloaded += 1
                except Exception as e:
                    if isinstance(e, urllib.error.HTTPError) and e.code in (404, 410):
                        skipped_missing += 1
                        continue

                    failed += 1
                    if print_errors and (error_limit <= 0 or printed_errors < error_limit):
                        self.stderr.write(
                            f"ERROR ingredient_media ingredient_id={ing_id} url={url} object_path={object_path} exc={type(e).__name__}: {e}"
                        )
                        printed_errors += 1
                    continue

                public_url = None
                if to_supabase_storage:
                    public_url = f"{supabase_public_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{object_path}"

                with transaction.atomic():
                    existing = MediaAsset.objects.filter(
                        metadata__ingredient_id=ing_id,
                        metadata__tag=tag,
                    ).first()

                    if existing:
                        reused_assets += 1
                    else:
                        MediaAsset.objects.create(
                            kind=MediaAsset.KIND_IMAGE,
                            scope=MediaAsset.SCOPE_WEB_OK_SMALL,
                            url=public_url or url,
                            local_path=None,
                            size_bytes=size_bytes,
                            mime_type=mime_type,
                            checksum=checksum,
                            metadata={
                                'tag': tag,
                                'source': 'example_data',
                                'entity': 'ingredient',
                                'ingredient_id': ing_id,
                                'ingredient_name': ing.get('name'),
                                'storage_bucket': bucket_name,
                                'storage_path': object_path,
                                'note': 'study',
                            },
                        )
                        created_assets += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. downloaded={downloaded}, skipped_missing={skipped_missing}, failed={failed}, created_assets={created_assets}, reused_assets={reused_assets}"
        ))
