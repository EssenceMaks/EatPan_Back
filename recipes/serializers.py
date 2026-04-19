from rest_framework import serializers
from .models import Recipe, RecipeBook, MediaAsset, RecipeCategory, UserRecipeState, RecipeComment, RecipeReaction, CommentReaction


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
        fields = ['id', 'uuid', 'data', 'media_assets', 'is_active', 'is_public', 'author_username', 'repost_count', 'share_count', 'created_at']

class RecipeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeCategory
        fields = ['uuid', 'data', 'created_at']

class UserRecipeStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRecipeState
        fields = '__all__'

class RecipeCommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    class Meta:
        model = RecipeComment
        fields = '__all__'

class RecipeReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeReaction
        fields = '__all__'

class CommentReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommentReaction
        fields = '__all__'
