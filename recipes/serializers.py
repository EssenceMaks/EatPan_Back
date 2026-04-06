from rest_framework import serializers
from .models import Recipe, RecipeBook, MediaAsset


class MediaAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaAsset
        fields = [
            'uuid',
            'kind',
            'scope',
            'url',
            'local_path',
            'size_bytes',
            'mime_type',
            'checksum',
            'metadata',
            'created_at',
            'updated_at',
        ]

class RecipeBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeBook
        fields = ['id', 'uuid', 'name', 'data', 'created_at', 'updated_at']

class RecipeSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    media_assets = MediaAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Recipe
        fields = ['id', 'uuid', 'data', 'media_assets', 'is_active', 'is_public', 'author_username', 'created_at']
