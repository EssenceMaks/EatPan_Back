from rest_framework import viewsets
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import Recipe, RecipeBook
from .serializers import RecipeSerializer, RecipeBookSerializer

class RecipeBookViewSet(viewsets.ModelViewSet):
    queryset = RecipeBook.objects.all().order_by('id')
    serializer_class = RecipeBookSerializer

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        """ Отримати ієрархію всіх Книг -> Груп -> Категорій (Закешовано) """
        return super().list(request, *args, **kwargs)

class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeSerializer

    def get_queryset(self):
        queryset = Recipe.objects.filter(is_active=True).order_by('-created_at')
        
        # Реалізуємо фільтрацію, якщо фронтенд клікає на папку в меню
        book = self.request.query_params.get('book')
        group = self.request.query_params.get('group')
        category = self.request.query_params.get('category')
        
        # Припускаємо, що рецепт зберігає 'books': [], 'group': 'String', 'category': 'String'
        if book:
            queryset = queryset.filter(data__books__contains=[book])
        if group:
            queryset = queryset.filter(data__group=group)
        if category:
            queryset = queryset.filter(data__category=category)
            
        return queryset

    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        """ Отримати список рецептів (з можливою фільтрацією вище) """
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 60))
    def retrieve(self, request, *args, **kwargs):
        """ Отримати конкретний рецепт по ID """
        return super().retrieve(request, *args, **kwargs)
