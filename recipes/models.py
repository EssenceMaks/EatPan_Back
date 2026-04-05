from django.db import models

class Recipe(models.Model):
    """
    Основна гнучка модель для зберігання рецептів у PostgreSQL.
    Використовує JSONField для підтримки складної ієрархії, що відповідає фронтенду (Figma: "Новий рецепт").
    
    Очікувана структура JSON (data):
    {
      "title": "Курячі нагетси",
      "short_description": "Хрусткі та дуже соковиті",
      "photo_url": "...",
      
      "categories": ["Птиця", "Супи"],  # Блок: КАТЕГОРІЯ
      "books": ["Всі рецепти", "Особисті", "Гості", "Заклади"], # Блок: ДОДАТИ ДО КНИГИ (Групи)
      
      "metadata": {
          "cooking_time_minutes": 45, 
          "portions": 4
      },
      
      "ingredients": [
          {"name": "Куряче філе", "amount": "500г"}
      ],
      "steps": [
          {"order": 1, "title": "МАРІНУВАННЯ", "description": "Наріжте філе кубиками..."}
      ],
      
      "chef_secret": "Для ідеальної хрусткості обваляйте нагетси...",
      "serving_recommendation": "Подавайте гарячими з медово-гірчичним соусом"
    }
    """
    # Єдина гнучка колонка для зберігання JSON-рецепту (у Postgres конвертується в JSONB)
    data = models.JSONField(verbose_name="Дані Рецепту (JSONB)", default=dict)
    
    author = models.ForeignKey(
        'auth.User', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name="recipes",
        verbose_name="Автор"
    )
    is_public = models.BooleanField(default=True, verbose_name="Публічний")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")
    is_active = models.BooleanField(default=True, verbose_name="Активний")

    class Meta:
        db_table = "recipes"
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепти"

    def __str__(self):
        # Безпечно отримуємо назву рецепту з JSONB, або показуємо ID
        return self.data.get("title", f"Рецепт #{self.id}")

class UserProfile(models.Model):
    """
    Додатковий профіль користувача для зберігання персональних даних (улюблені рецепти, задачі тощо).
    """
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name="profile", verbose_name="Користувач")
    liked_recipes = models.ManyToManyField(Recipe, blank=True, related_name="liked_by", verbose_name="Улюблені рецепти")
    tasks = models.JSONField(verbose_name="Задачі користувача", default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "user_profiles"
        verbose_name = "Профіль користувача"
        verbose_name_plural = "Профілі користувачів"

    def __str__(self):
        return f"Профіль: {self.user.username}"

class RecipeBook(models.Model):
    """
    Модель для зберігання ієрархії (Таксономії) рецептів.
    Книги -> Групи -> Категорії.
    """
    name = models.CharField(max_length=255, verbose_name="Назва книги", unique=True)
    data = models.JSONField(verbose_name="Структура (Групи, Категорії)", default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        db_table = "recipe_books"
        verbose_name = "Книга рецептів"
        verbose_name_plural = "Книги рецептів"

    def __str__(self):
        return self.name

