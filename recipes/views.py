import os
import uuid as uuid_mod
import urllib.request
import logging

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import Recipe, RecipeBook, MediaAsset
from .serializers import RecipeSerializer, RecipeBookSerializer
from .sync_outbox import outbox_enqueue

from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)

class RecipeBookViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = RecipeBook.objects.all().order_by('id')
    serializer_class = RecipeBookSerializer
    pagination_class = None

    def perform_create(self, serializer):
        obj = serializer.save()
        outbox_enqueue(
            entity_type='recipe_book',
            entity_uuid=obj.uuid,
            op='upsert',
            payload={
                'uuid': str(obj.uuid),
                'name': obj.name,
                'data': obj.data,
            },
        )

    def perform_update(self, serializer):
        obj = serializer.save()
        outbox_enqueue(
            entity_type='recipe_book',
            entity_uuid=obj.uuid,
            op='upsert',
            payload={
                'uuid': str(obj.uuid),
                'name': obj.name,
                'data': obj.data,
            },
        )

    def perform_destroy(self, instance):
        u = instance.uuid
        super().perform_destroy(instance)
        outbox_enqueue(
            entity_type='recipe_book',
            entity_uuid=u,
            op='delete',
            payload={'uuid': str(u)},
        )

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        """ Отримати ієрархію всіх Книг -> Груп -> Категорій (Закешовано) """
        return super().list(request, *args, **kwargs)

from rest_framework.decorators import action
from django.db.models import Q
from .models import UserProfile

class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'list' and self.request.query_params.get('fields') == 'light':
            from .serializers import RecipeListSerializer
            return RecipeListSerializer
        return RecipeSerializer

    def get_queryset(self):
        # Return recipes that are public OR authored by the current user
        queryset = Recipe.objects.filter(is_active=True)
        if self.request.user.is_authenticated:
            queryset = queryset.filter(Q(is_public=True) | Q(author=self.request.user))
        else:
            queryset = queryset.filter(is_public=True)
            
        queryset = queryset.order_by('-created_at')
        
        book = self.request.query_params.get('book')
        group = self.request.query_params.get('group')
        category = self.request.query_params.get('category')
        
        if book:
            queryset = queryset.filter(data__books__contains=[book])
        if group:
            if group == 'Без групи':
                queryset = queryset.filter(Q(data__books=[]) | Q(data__books__isnull=True))
            else:
                queryset = queryset.filter(data__books__contains=[group])
        if category:
            # Check both legacy string 'category' and new array 'categories'
            queryset = queryset.filter(Q(data__category=category) | Q(data__categories__contains=[category]))
            
        return queryset

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            obj = serializer.save(author=self.request.user, is_public=False)
        else:
            obj = serializer.save()

        # Auto-link orphan MediaAssets by UUID from data.media.images
        media_uuids = (obj.data or {}).get('media', {}).get('images', [])
        if media_uuids:
            # Filter only valid UUIDs (not URLs)
            valid_uuids = [u for u in media_uuids if not str(u).startswith('http')]
            if valid_uuids:
                linked = MediaAsset.objects.filter(
                    uuid__in=valid_uuids, recipe__isnull=True
                ).update(recipe=obj)
                logger.info(f'Auto-linked {linked} MediaAssets to recipe {obj.id}')

        outbox_enqueue(
            entity_type='recipe',
            entity_uuid=obj.uuid,
            op='upsert',
            payload={
                'uuid': str(obj.uuid),
                'data': obj.data,
                'is_active': obj.is_active,
                'is_public': obj.is_public,
            },
        )

    def perform_update(self, serializer):
        obj = serializer.save()
        outbox_enqueue(
            entity_type='recipe',
            entity_uuid=obj.uuid,
            op='upsert',
            payload={
                'uuid': str(obj.uuid),
                'data': obj.data,
                'is_active': obj.is_active,
                'is_public': obj.is_public,
            },
        )

    def perform_destroy(self, instance):
        u = instance.uuid
        super().perform_destroy(instance)
        outbox_enqueue(
            entity_type='recipe',
            entity_uuid=u,
            op='delete',
            payload={'uuid': str(u)},
        )

    from django.views.decorators.vary import vary_on_headers
    @method_decorator(cache_page(60 * 5))
    @method_decorator(vary_on_headers('Authorization', 'Cookie'))
    def list(self, request, *args, **kwargs):
        """ Отримати список рецептів (кешування увімкнено) """
        return super().list(request, *args, **kwargs)

    # @method_decorator(cache_page(60 * 60))
    def retrieve(self, request, *args, **kwargs):
        """ Отримати конкретний рецепт по ID """
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='toggle_like')
    def toggle_like(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'error': 'Unauthorized'}, status=401)
        recipe = self.get_object()
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        
        if recipe in profile.liked_recipes.all():
            profile.liked_recipes.remove(recipe)
            liked = False
        else:
            profile.liked_recipes.add(recipe)
            liked = True

        outbox_enqueue(
            entity_type='user_profile',
            entity_uuid=profile.uuid,
            op='patch',
            payload={
                'uuid': str(profile.uuid),
                'liked_recipe_uuids': [str(r.uuid) for r in profile.liked_recipes.all().only('uuid')],
            },
        )
        return Response({'liked': liked, 'recipe_id': recipe.id})

from .models import RecipeCategory, UserRecipeState, RecipeComment, RecipeReaction, CommentReaction
from .serializers import RecipeCategorySerializer, UserRecipeStateSerializer, RecipeCommentSerializer, RecipeReactionSerializer, CommentReactionSerializer

import uuid

class RecipeCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = RecipeCategory.objects.all().order_by('id')
    serializer_class = RecipeCategorySerializer
    pagination_class = None

    def perform_create(self, serializer):
        instance = serializer.save()
        outbox_enqueue(
            entity_type='recipe_category',
            entity_uuid=instance.uuid,
            op='upsert',
            payload={'data': instance.data},
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        outbox_enqueue(
            entity_type='recipe_category',
            entity_uuid=instance.uuid,
            op='upsert',
            payload={'data': instance.data},
        )

    def perform_destroy(self, instance):
        outbox_enqueue(
            entity_type='recipe_category',
            entity_uuid=instance.uuid,
            op='delete',
            payload={},
        )
        instance.delete()

class UserRecipeStateViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = UserRecipeState.objects.all()
    serializer_class = UserRecipeStateSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        outbox_enqueue(
            entity_type='user_recipe_state',
            entity_uuid=instance.uuid,
            op='upsert',
            payload={
                'user_id': instance.user_id,
                'recipe_uuid': str(instance.recipe.uuid),
                'is_planned': instance.is_planned,
                'is_cooked': instance.is_cooked,
                'cooked_date': instance.cooked_date.isoformat() if instance.cooked_date else None,
                'expiration_date': instance.expiration_date.isoformat() if instance.expiration_date else None,
                'location': instance.location,
                'cook_count': instance.cook_count,
                'personal_digestion_time': instance.personal_digestion_time,
            },
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        outbox_enqueue(
            entity_type='user_recipe_state',
            entity_uuid=instance.uuid,
            op='upsert',
            payload={
                'user_id': instance.user_id,
                'recipe_uuid': str(instance.recipe.uuid),
                'is_planned': instance.is_planned,
                'is_cooked': instance.is_cooked,
                'cooked_date': instance.cooked_date.isoformat() if instance.cooked_date else None,
                'expiration_date': instance.expiration_date.isoformat() if instance.expiration_date else None,
                'location': instance.location,
                'cook_count': instance.cook_count,
                'personal_digestion_time': instance.personal_digestion_time,
            },
        )

    def perform_destroy(self, instance):
        outbox_enqueue(
            entity_type='user_recipe_state',
            entity_uuid=instance.uuid,
            op='delete',
            payload={'user_id': instance.user_id, 'recipe_uuid': str(instance.recipe.uuid)},
        )
        instance.delete()

class RecipeCommentViewSet(viewsets.ModelViewSet):
    queryset = RecipeComment.objects.all().order_by('-created_at')
    serializer_class = RecipeCommentSerializer

    def perform_create(self, serializer):
        instance = serializer.save(author=self.request.user)
        outbox_enqueue(
            entity_type='recipe_comment',
            entity_uuid=instance.uuid,
            op='upsert',
            payload={
                'author_id': instance.author_id,
                'recipe_uuid': str(instance.recipe.uuid),
                'text': instance.text,
            },
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        outbox_enqueue(
            entity_type='recipe_comment',
            entity_uuid=instance.uuid,
            op='upsert',
            payload={
                'author_id': instance.author_id,
                'recipe_uuid': str(instance.recipe.uuid),
                'text': instance.text,
            },
        )

    def perform_destroy(self, instance):
        outbox_enqueue(
            entity_type='recipe_comment',
            entity_uuid=instance.uuid,
            op='delete',
            payload={'author_id': instance.author_id, 'recipe_uuid': str(instance.recipe.uuid)},
        )
        instance.delete()

class RecipeReactionViewSet(viewsets.ModelViewSet):
    queryset = RecipeReaction.objects.all()
    serializer_class = RecipeReactionSerializer

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)
        # Generate consistent UUID for outbox
        virtual_uuid = uuid.uuid5(uuid.NAMESPACE_OID, f"rec_react_{instance.recipe.id}_{instance.user.id}_{instance.emoji_type}")
        outbox_enqueue(
            entity_type='recipe_reaction',
            entity_uuid=virtual_uuid,
            op='upsert',
            payload={
                'user_id': instance.user_id,
                'recipe_uuid': str(instance.recipe.uuid),
                'emoji_type': instance.emoji_type,
            },
        )

    def perform_destroy(self, instance):
        virtual_uuid = uuid.uuid5(uuid.NAMESPACE_OID, f"rec_react_{instance.recipe.id}_{instance.user.id}_{instance.emoji_type}")
        outbox_enqueue(
            entity_type='recipe_reaction',
            entity_uuid=virtual_uuid,
            op='delete',
            payload={
                'user_id': instance.user_id,
                'recipe_uuid': str(instance.recipe.uuid),
                'emoji_type': instance.emoji_type,
            },
        )
        instance.delete()

class CommentReactionViewSet(viewsets.ModelViewSet):
    queryset = CommentReaction.objects.all()
    serializer_class = CommentReactionSerializer

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)
        virtual_uuid = uuid.uuid5(uuid.NAMESPACE_OID, f"com_react_{instance.comment.id}_{instance.user.id}_{instance.emoji_type}")
        outbox_enqueue(
            entity_type='comment_reaction',
            entity_uuid=virtual_uuid,
            op='upsert',
            payload={
                'user_id': instance.user_id,
                'comment_uuid': str(instance.comment.uuid),
                'emoji_type': instance.emoji_type,
            },
        )

    def perform_destroy(self, instance):
        virtual_uuid = uuid.uuid5(uuid.NAMESPACE_OID, f"com_react_{instance.comment.id}_{instance.user.id}_{instance.emoji_type}")
        outbox_enqueue(
            entity_type='comment_reaction',
            entity_uuid=virtual_uuid,
            op='delete',
            payload={
                'user_id': instance.user_id,
                'comment_uuid': str(instance.comment.uuid),
                'emoji_type': instance.emoji_type,
            },
        )
        instance.delete()


class MediaUploadView(APIView):
    """
    Приймає файл від фронтенда, перенаправляє в Local Supabase Storage
    (контейнер supabase-storage через kong:8000), створює запис MediaAsset.
    
    POST /api/v1/media/upload/
    Body: multipart/form-data with 'file' field
    Optional: 'recipe_id' to link to existing recipe
    Returns: { uuid, url }
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        recipe_id = request.data.get('recipe_id')

        if not file:
            return Response({'error': 'No file provided'}, status=400)

        asset_uuid = uuid_mod.uuid4()
        clean_name = file.name or 'image.jpg'
        storage_path = f"study/recipes/{asset_uuid}/{clean_name}"

        # Read env vars for local Supabase Storage connection
        supabase_url = os.environ.get('SUPABASE_URL', 'http://kong:8000').rstrip('/')
        public_url_base = os.environ.get('SUPABASE_PUBLIC_URL', 'http://localhost:6500').rstrip('/')
        service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
        bucket = os.environ.get('SUPABASE_MEDIA_BUCKET', 'id_eatpan_media')

        if not service_key:
            return Response({'error': 'Storage not configured (missing SUPABASE_SERVICE_ROLE_KEY)'}, status=500)

        # Read file bytes
        file_bytes = file.read()

        # Forward to Local Supabase Storage via REST API
        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{storage_path}"
        try:
            req = urllib.request.Request(
                upload_url,
                data=file_bytes,
                method='PUT',
                headers={
                    'Authorization': f'Bearer {service_key}',
                    'apikey': service_key,
                    'Content-Type': file.content_type or 'application/octet-stream',
                    'x-upsert': 'true',
                },
            )
            urllib.request.urlopen(req, timeout=60)
        except Exception as e:
            logger.error(f'Failed to upload to Supabase Storage: {e}')
            return Response({'error': f'Storage upload failed: {str(e)}'}, status=502)

        # Build public URL (for local access via localhost:6500)
        public_url = f"{public_url_base}/storage/v1/object/public/{bucket}/{storage_path}"

        # Optionally link to recipe
        recipe = None
        if recipe_id:
            recipe = Recipe.objects.filter(id=recipe_id).first()

        # Create MediaAsset record in PostgreSQL
        asset = MediaAsset.objects.create(
            uuid=asset_uuid,
            kind=MediaAsset.KIND_IMAGE,
            scope=MediaAsset.SCOPE_LOCAL_ONLY,
            url=public_url,
            size_bytes=len(file_bytes),
            mime_type=file.content_type,
            metadata={
                'storage_bucket': bucket,
                'storage_path': storage_path,
                'original_name': clean_name,
            },
            recipe=recipe,
            owner=request.user if request.user.is_authenticated else None,
        )

        logger.info(f'MediaAsset created: uuid={asset.uuid}, path={storage_path}, size={len(file_bytes)}')

        return Response({
            'uuid': str(asset.uuid),
            'url': public_url,
        }, status=201)
