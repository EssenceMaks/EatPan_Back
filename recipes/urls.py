from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RecipeViewSet, RecipeBookViewSet, RecipeCategoryViewSet, UserRecipeStateViewSet, RecipeCommentViewSet, RecipeReactionViewSet, CommentReactionViewSet, MediaUploadView

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')
router.register(r'recipe-books', RecipeBookViewSet, basename='recipebook')
router.register(r'categories', RecipeCategoryViewSet, basename='category')
router.register(r'user-recipe-states', UserRecipeStateViewSet, basename='userrecipestate')
router.register(r'comments', RecipeCommentViewSet, basename='comment')
router.register(r'reactions/recipe', RecipeReactionViewSet, basename='recipereaction')
router.register(r'reactions/comment', CommentReactionViewSet, basename='commentreaction')

urlpatterns = [
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
    path('', include(router.urls)),
]
