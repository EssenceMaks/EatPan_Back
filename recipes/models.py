import uuid

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
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
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
    
    repost_count = models.IntegerField(default=0, verbose_name="Кількість репостів")
    share_count = models.IntegerField(default=0, verbose_name="Кількість відправок")

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
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name="profile", verbose_name="Користувач")
    liked_recipes = models.ManyToManyField(Recipe, blank=True, related_name="liked_by", verbose_name="Улюблені рецепти")
    tasks = models.JSONField(verbose_name="Задачі користувача", default=dict, blank=True)
    
    account = models.JSONField(default=dict, blank=True, verbose_name="Account Settings")
    meal_plan = models.JSONField(default=dict, blank=True, verbose_name="Meal Plan Data")
    pantry = models.JSONField(default=dict, blank=True, verbose_name="Pantry Inventory")
    shopping = models.JSONField(default=dict, blank=True, verbose_name="Shopping Lists")
    social = models.JSONField(default=dict, blank=True, verbose_name="Social Context")
    inbox = models.JSONField(default=dict, blank=True, verbose_name="Messages & Notifications")
    user_data = models.JSONField(default=dict, blank=True, verbose_name="Generic User Data")

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
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
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


class MediaAsset(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    KIND_IMAGE = 'image'
    KIND_VIDEO = 'video'
    KIND_AUDIO = 'audio'
    KIND_FILE = 'file'
    KIND_CHOICES = [
        (KIND_IMAGE, 'Image'),
        (KIND_VIDEO, 'Video'),
        (KIND_AUDIO, 'Audio'),
        (KIND_FILE, 'File'),
    ]

    SCOPE_LOCAL_ONLY = 'local_only'
    SCOPE_WEB_OK_SMALL = 'web_ok_small'
    SCOPE_CHOICES = [
        (SCOPE_LOCAL_ONLY, 'Local only'),
        (SCOPE_WEB_OK_SMALL, 'Web ok (small)'),
    ]

    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default=SCOPE_LOCAL_ONLY)

    url = models.URLField(blank=True, null=True)
    local_path = models.CharField(max_length=1024, blank=True, null=True)
    size_bytes = models.BigIntegerField(blank=True, null=True)
    mime_type = models.CharField(max_length=255, blank=True, null=True)
    checksum = models.CharField(max_length=128, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    owner = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='media_assets')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, null=True, blank=True, related_name='media_assets')
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='media_assets')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'media_assets'

    def __str__(self):
        return f"{self.kind}:{self.uuid}"

class RecipeCategory(models.Model):
    """
    Гнучка модель для зберігання Категорій та їх налаштувань.
    Використовує JSONField для імені, іконки, кольору та інших властивостей.
    """
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    data = models.JSONField(verbose_name="Дані категорії (JSONB)", default=dict)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")

    class Meta:
        db_table = "recipe_categories"
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"

    def __str__(self):
        return self.data.get("name", f"Категорія #{self.id}")

class UserRecipeState(models.Model):
    """Відстеження взаємодії користувача з рецептом (Сплановано, Приготовлено тощо)."""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name="recipe_states")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="user_states")
    
    is_planned = models.BooleanField(default=False, verbose_name="Сплановано")
    is_cooked = models.BooleanField(default=False, verbose_name="Приготовлено")
    cooked_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата приготування")
    expiration_date = models.DateTimeField(null=True, blank=True, verbose_name="Строк придатності")
    
    location = models.CharField(max_length=255, blank=True, verbose_name="Локація (Холодильник, шафа)")
    cook_count = models.IntegerField(default=0, verbose_name="Кількість приготувань юзером")
    personal_digestion_time = models.CharField(max_length=100, blank=True, verbose_name="Час засвоювання (особистий)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_recipe_states"
        unique_together = ('user', 'recipe')

class RecipeComment(models.Model):
    """Коментарі до рецепту"""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name="recipe_comments")
    text = models.TextField(verbose_name="Текст коментаря")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recipe_comments"
        ordering = ['-created_at']

class RecipeReaction(models.Model):
    """Додаткові емодзі-реакції на Рецепт (крім стандартного лайку)"""
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name="recipe_reactions")
    emoji_type = models.CharField(max_length=50, verbose_name="Тип емодзі (напр. fire, star)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recipe_reactions"
        unique_together = ('recipe', 'user', 'emoji_type')

class CommentReaction(models.Model):
    """Емодзі-реакції на Коментар"""
    comment = models.ForeignKey(RecipeComment, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name="comment_reactions")
    emoji_type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comment_reactions"
        unique_together = ('comment', 'user', 'emoji_type')



class SyncOutbox(models.Model):
    entity_type = models.CharField(max_length=64)
    entity_uuid = models.UUIDField(db_index=True)
    op = models.CharField(max_length=16)
    payload = models.JSONField(default=dict, blank=True)
    node_id = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'sync_outbox'
        indexes = [
            models.Index(fields=['entity_type', 'published_at', 'created_at']),
        ]

    def __str__(self):
        return f"Outbox #{self.id} [{self.entity_type}:{self.op}]"

class PromoCode(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='created_promos')
    discount_pct = models.IntegerField(default=0)
    
    PROMO_TYPE_CHOICES = (
        ('discount', 'Discount'),
        ('gift', 'Gift'),
    )
    promo_type = models.CharField(max_length=20, choices=PROMO_TYPE_CHOICES, default='discount')
    linked_recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True, blank=True)
    max_uses = models.IntegerField(default=1)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "promo_codes"

class PromoCodeUsage(models.Model):
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='promo_usages')
    used_at = models.DateTimeField(auto_now_add=True)
    gifted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='gifted_promos')
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "promo_code_usages"

