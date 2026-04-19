from rest_framework import serializers
from .models import (
    Recipe, RecipeBook, MediaAsset, RecipeCategory, UserRecipeState,
    RecipeComment, RecipeReaction, CommentReaction, UserProfile,
    PromoCode, PromoCodeUsage
)


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

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'uuid', 'username', 'liked_recipes', 'tasks',
            'account', 'meal_plan', 'pantry', 'shopping',
            'social', 'inbox', 'user_data', 'created_at', 'updated_at'
        ]

class PublicProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['uuid', 'username', 'account', 'social']

class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = '__all__'

class PromoCodeUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCodeUsage
        fields = '__all__'

class RecipeListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for lists to optimize payload size.
    Extracts essential fields from the 'data' JSONB.
    """
    title = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    prep_time = serializers.SerializerMethodField()
    image_uuid = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Recipe
        fields = ['id', 'uuid', 'title', 'category', 'prep_time', 'image_uuid', 'author_username', 'is_public', 'repost_count', 'share_count']

    def get_title(self, obj):
        if not isinstance(obj.data, dict):
            return ''
        return obj.data.get('title', '')

    def get_category(self, obj):
        if not isinstance(obj.data, dict):
            return []
        # Prefer the structured 'categories' array (new standard)
        cats = obj.data.get('categories', [])
        if isinstance(cats, list) and len(cats) > 0:
            return cats
        # Fallback to legacy 'category' string (may be comma-separated)
        cat = obj.data.get('category', '')
        if isinstance(cat, str) and cat.strip():
            # Filter out numeric-only values (likely cooking times stored in wrong field)
            parts = [p.strip() for p in cat.split(',') if p.strip() and not p.strip().isdigit()]
            return parts
        return []

    def get_prep_time(self, obj):
        if not isinstance(obj.data, dict):
            return ''
        # Check multiple possible fields for cooking time
        t = obj.data.get('prep_time', '')
        if not t:
            t = obj.data.get('time_str', '')
        if not t:
            meta = obj.data.get('metadata', {})
            if isinstance(meta, dict):
                minutes = meta.get('cooking_time_minutes')
                if minutes:
                    t = str(minutes)
        return t or ''

    def get_image_uuid(self, obj):
        if not isinstance(obj.data, dict):
            return None
            
        # 1. Look in media_assets first (preferred as it's the new standard)
        # Uses prefetch_related cache
        assets = list(obj.media_assets.all())
        if assets:
            return str(assets[0].uuid)
            
        # 2. Fallback to parsing images[0]
        images = obj.data.get('media', {}).get('images', [])
        image_ref = images[0] if images else None
        
        # 3. Fallback legacy fields
        if not image_ref:
            image_ref = obj.data.get('image_url') or obj.data.get('image')
            
        return image_ref

