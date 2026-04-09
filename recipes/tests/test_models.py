import pytest
from django.contrib.auth.models import User
from recipes.models import Recipe, UserProfile, RecipeBook, MediaAsset, SyncOutbox

@pytest.mark.django_db
def test_recipe_str():
    recipe = Recipe.objects.create(data={"title": "Test Recipe"})
    assert str(recipe) == "Test Recipe"
    
    recipe_no_title = Recipe.objects.create(data={})
    assert str(recipe_no_title) == f"Рецепт #{recipe_no_title.id}"

@pytest.mark.django_db
def test_user_profile_str():
    user = User.objects.create(username="testuser")
    profile = UserProfile.objects.create(user=user)
    assert str(profile) == "Профіль: testuser"

@pytest.mark.django_db
def test_recipe_book_str():
    book = RecipeBook.objects.create(name="My Book")
    assert str(book) == "My Book"

@pytest.mark.django_db
def test_media_asset_str():
    asset = MediaAsset.objects.create(kind=MediaAsset.KIND_IMAGE)
    assert str(asset) == f"image:{asset.uuid}"
