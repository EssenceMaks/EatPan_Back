from recipes.models import Recipe  
Recipe.objects.all().update(is_public=True)  
print("Marked all recipes as public")  
