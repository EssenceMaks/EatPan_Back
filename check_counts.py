import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from recipes.models import Recipe, RecipeCategory, MediaAsset

print(f"Local recipes: {Recipe.objects.count()}")
print(f"Cloud recipes: {Recipe.objects.using('cloud').count()}")
print(f"Local categories: {RecipeCategory.objects.count()}")
print(f"Cloud categories: {RecipeCategory.objects.using('cloud').count()}")
print(f"Local media: {MediaAsset.objects.count()}")
print(f"Cloud media: {MediaAsset.objects.using('cloud').count()}")
