from recipes.models import Recipe
count = 0
for r in Recipe.objects.all():
    if "category" in r.data and "categories" not in r.data:
        r.data["categories"] = [r.data["category"]]
        r.save()
        count += 1
print(f"Migrated categories for {count} recipes")
