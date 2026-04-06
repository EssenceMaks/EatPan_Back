from rest_framework import viewsets
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import Recipe, RecipeBook
from .serializers import RecipeSerializer, RecipeBookSerializer
from .sync_outbox import outbox_enqueue

class RecipeBookViewSet(viewsets.ModelViewSet):
    queryset = RecipeBook.objects.all().order_by('id')
    serializer_class = RecipeBookSerializer

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
    serializer_class = RecipeSerializer

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
            queryset = queryset.filter(data__group=group)
        if category:
            queryset = queryset.filter(data__category=category)
            
        return queryset

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            # Mark frontend-created recipes as not public initially, and tie to author
            obj = serializer.save(author=self.request.user, is_public=False)
        else:
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

    # @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        """ Отримати список рецептів (кешування вимкнено для авторизації) """
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
