from rest_framework import serializers
from .models import Recipe, RecipeBook

class RecipeBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeBook
        fields = ['id', 'name', 'data', 'created_at', 'updated_at']

class RecipeSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Recipe
        fields = ['id', 'data', 'is_active', 'is_public', 'author_username', 'created_at']
