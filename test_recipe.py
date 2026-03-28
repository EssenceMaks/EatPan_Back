import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from recipes.models import Recipe

recipe_data = {
  "title": "Курячі нагетси",
  "short_description": "Хрусткі та дуже соковиті",
  "photo_url": "https://example.com/photo.jpg",
  "categories": ["Птиця", "М'ясо"],
  "books": ["Всі рецепти", "Особисті"],
  "metadata": {
      "cooking_time_minutes": 45, 
      "portions": 4
  },
  "ingredients": [
      {"name": "Куряче філе", "amount": "500г"},
      {"name": "Імбирна паста", "amount": "1 ч.л."},
      {"name": "Соєвий соус", "amount": "1 ст.л."}
  ],
  "steps": [
      {"order": 1, "title": "МАРІНУВАННЯ", "description": "Наріжте філе кубиками, змішайте зі спеціями та соусом. Залиште на 20 хвилин."},
      {"order": 2, "title": "ПАНІРУВАННЯ", "description": "Сформуйте нагетси, вмочіть у яйце, а потім щільно обваляйте в сухарях."}
  ],
  "chef_secret": "Для ідеальної хрусткості обваляйте нагетси в сухарях двічі, охолоджуючи їх між етапами.",
  "serving_recommendation": "Подавайте гарячими з медово-гірчичним соусом або домашнім кетчупом для розкриття смаку."
}

# Створюємо в БД
r = Recipe.objects.create(data=recipe_data)
print(f"DATABASE VERIFICATION SUCCESS: Saved '{r}' directly to Supabase PostgreSQL!")
