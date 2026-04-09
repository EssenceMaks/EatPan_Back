import pytest
from django.contrib.auth.models import User
from recipes.models import Recipe, RecipeBook, MediaAsset
from recipes.serializers import RecipeSerializer, RecipeBookSerializer, MediaAssetSerializer

@pytest.mark.django_db
def test_recipe_book_serializer():
    book = RecipeBook.objects.create(name="Desserts", data={"categories": ["Cakes"]})
    serializer = RecipeBookSerializer(book)
    data = serializer.data
    
    assert data["name"] == "Desserts"
    assert data["data"] == {"categories": ["Cakes"]}
    assert "uuid" in data
    assert "created_at" in data
    assert "updated_at" in data

@pytest.mark.django_db
def test_media_asset_serializer():
    asset = MediaAsset.objects.create(
        kind=MediaAsset.KIND_IMAGE,
        url="http://example.com/image.jpg",
        size_bytes=1024,
        mime_type="image/jpeg"
    )
    serializer = MediaAssetSerializer(asset)
    data = serializer.data
    
    assert data["kind"] == "image"
    assert data["url"] == "http://example.com/image.jpg"
    assert data["size_bytes"] == 1024
    assert data["mime_type"] == "image/jpeg"
    assert "uuid" in data

@pytest.mark.django_db
def test_recipe_serializer():
    user = User.objects.create(username="chef")
    recipe = Recipe.objects.create(
        data={"title": "Cake"},
        author=user,
        is_public=True
    )
    serializer = RecipeSerializer(recipe)
    data = serializer.data
    
    assert data["data"] == {"title": "Cake"}
    assert data["author_username"] == "chef"
    assert data["is_public"] is True
    assert data["media_assets"] == []
    assert "uuid" in data
