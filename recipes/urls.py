from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RecipeViewSet, RecipeBookViewSet

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')
router.register(r'recipe-books', RecipeBookViewSet, basename='recipebook')

urlpatterns = [
    path('', include(router.urls)),
]
