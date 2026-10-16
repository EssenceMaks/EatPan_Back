"""
views_ingredients.py — API для інгредієнтів.

GET  /api/v1/ingredients/                 — список (з пагінацією)
GET  /api/v1/ingredients/?search=garl     — пошук по назві
GET  /api/v1/ingredients/?locale=uk       — з перекладом
GET  /api/v1/ingredients/<uuid>/          — деталі інгредієнта
POST /api/v1/ingredients/                 — створити новий (unverified)
"""

import re

import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q

from .models import Ingredient, IngredientTranslation


SUPABASE_PUBLIC_URL = os.environ.get("SUPABASE_PUBLIC_URL", "http://localhost:6500")
SUPABASE_MEDIA_BUCKET = os.environ.get("SUPABASE_MEDIA_BUCKET", "id_eatpan_media")


def build_photo_url(media: dict) -> str | None:
    """Build full public URL for ingredient photo."""
    photo_path = media.get("photo") if media else None
    if not photo_path:
        return None
    return f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{SUPABASE_MEDIA_BUCKET}/{photo_path}"


def serialize_ingredient(ing: Ingredient, locale: str = None) -> dict:
    """Serialize an ingredient to dict, optionally with locale translation."""
    data = {
        "uuid": str(ing.uuid),
        "name": ing.name,
        "slug": ing.slug,
        "category": ing.category,
        "photo_url": build_photo_url(ing.media),
        "source": ing.source,
        "name_status": ing.name_status,
        "possible_units": ing.possible_units,
        "market_data": ing.market_data,
    }

    # Add translated name if locale specified
    if locale and locale != "en":
        try:
            trans = IngredientTranslation.objects.get(ingredient=ing, locale=locale)
            data["translated_name"] = trans.name
        except IngredientTranslation.DoesNotExist:
            data["translated_name"] = None

    return data


class IngredientListView(APIView):
    """
    GET /api/v1/ingredients/
    Query params:
      - search: фільтр по назві (icontains на en + locale)
      - locale: мова перекладу (uk, es, pl, ...)
      - source: фільтр по джерелу (catalog, eatpan, user)
      - category: фільтр по категорії
      - has_photo=1: тільки інгредієнти з фото
      - fields=light: тільки назва, переклад і фото (індекс фото для фронтенду)
      - limit: кількість (default 50, max 2000)
      - offset: зсув пагінації
    """
    permission_classes = [AllowAny]

    def get(self, request):
        search = request.query_params.get("search", "").strip()
        locale = request.query_params.get("locale", "").strip()
        source = request.query_params.get("source", "").strip()
        category = request.query_params.get("category", "").strip()
        has_photo = request.query_params.get("has_photo", "").strip() in ("1", "true")
        light = request.query_params.get("fields", "").strip() == "light"
        limit = min(int(request.query_params.get("limit", 50)), 2000)
        offset = int(request.query_params.get("offset", 0))

        qs = Ingredient.objects.all()

        # Filters
        if source:
            qs = qs.filter(source=source)
        if category:
            qs = qs.filter(category__icontains=category)
        if has_photo:
            qs = qs.filter(media__photo__isnull=False).exclude(media__photo=None)

        # Search (across English name + ALL locale translations)
        if search:
            q = Q(name__icontains=search)
            trans_ids = IngredientTranslation.objects.filter(
                name__icontains=search
            ).values_list("ingredient_id", flat=True)
            q |= Q(id__in=trans_ids)
            qs = qs.filter(q).distinct()

        total = qs.count()
        ingredients = qs.order_by("name")[offset:offset + limit]

        if light:
            page = list(ingredients)
            names = {}
            if locale and locale != "en":
                names = dict(IngredientTranslation.objects.filter(
                    ingredient__in=page, locale=locale
                ).values_list("ingredient_id", "name"))
            results = [{
                "name": ing.name,
                "translated_name": names.get(ing.id),
                "photo_url": build_photo_url(ing.media),
            } for ing in page]
        else:
            results = [serialize_ingredient(ing, locale) for ing in ingredients]

        return Response({
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": results,
        })

    def post(self, request):
        """
        POST /api/v1/ingredients/
        Body: { "name": "Kefir", "locale": "uk" }
        Creates a new unverified ingredient if it doesn't exist.
        Returns the existing ingredient if it does.
        """
        name = request.data.get("name", "").strip()
        locale = request.data.get("locale", "en").strip()

        if not name:
            return Response({"error": "name is required"}, status=400)

        # Normalize for lookup
        name_lower = name.lower()
        slug = re.sub(r"[''']", "", name_lower)
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")

        # Check if already exists (by name or slug)
        existing = Ingredient.objects.filter(
            Q(name=name_lower) | Q(slug=slug)
        ).first()

        if existing:
            return Response(serialize_ingredient(existing, locale), status=200)

        # Create new unverified ingredient
        ing = Ingredient.objects.create(
            name=name_lower,
            slug=slug,
            source="user",
            name_status="unverified",
            created_locale=locale,
        )

        # Create translation in the user's locale
        IngredientTranslation.objects.create(
            ingredient=ing,
            locale=locale,
            name=name_lower,
            is_primary=True,
        )

        # Also create English translation if locale is not English
        if locale != "en":
            IngredientTranslation.objects.create(
                ingredient=ing,
                locale="en",
                name=name_lower,
                is_primary=False,
            )

        return Response(serialize_ingredient(ing, locale), status=201)


class IngredientDetailView(APIView):
    """
    GET /api/v1/ingredients/<uuid>/
    Returns full ingredient details with all available translations.
    """
    permission_classes = [AllowAny]

    def get(self, request, ingredient_uuid):
        try:
            ing = Ingredient.objects.get(uuid=ingredient_uuid)
        except Ingredient.DoesNotExist:
            return Response({"error": "Ingredient not found"}, status=404)

        data = serialize_ingredient(ing)
        data["nutrition"] = ing.nutrition
        data["media"] = ing.media

        # All translations
        translations = {}
        for t in ing.translations.all():
            translations[t.locale] = {
                "name": t.name,
                "is_primary": t.is_primary,
            }
        data["translations"] = translations

        return Response(data)
