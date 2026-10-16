"""
populate_ingredients.py — Django management command.
Наповнює таблицю ingredients (~957 записів) та ingredient_translations (en).

Запуск: docker exec django_api python manage.py populate_ingredients
"""

import json
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from recipes.models import Ingredient, IngredientTranslation


def slugify_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[''']", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


class Command(BaseCommand):
    help = "Populate ingredients table from Spoonacular + EatPan mapping"

    def handle(self, *args, **options):
        base_dir = Path("/app")
        script_dir = base_dir.parent / "spoonacular-script"

        # Fallback paths for different setups
        if not script_dir.exists():
            script_dir = Path(__file__).resolve().parent.parent.parent.parent / "spoonacular-script"

        base_json = script_dir / "ingredients_base.json"
        mapping_json = script_dir / "ingredient_mapping.json"

        if not base_json.exists():
            self.stderr.write(f"ERROR: {base_json} not found")
            return

        if not mapping_json.exists():
            self.stderr.write(f"ERROR: {mapping_json} not found. Run normalize_ingredients.py first.")
            return

        with open(base_json, "r", encoding="utf-8") as f:
            spoon_data = json.load(f)

        with open(mapping_json, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        self.stdout.write(f"Loaded {len(spoon_data)} Spoonacular entries")
        self.stdout.write(f"Mapping summary: {json.dumps(mapping['_summary'], indent=2)}")

        created_count = 0
        skipped_count = 0
        translation_count = 0

        # ── Phase 1: Spoonacular base ingredients ──
        self.stdout.write("\n--- Phase 1: Spoonacular ingredients ---")
        for entry in spoon_data:
            name = entry["name_en"].lower().strip()
            slug = slugify_name(name)

            if Ingredient.objects.filter(name=name).exists():
                skipped_count += 1
                continue

            # Build media paths
            photo_path = None
            img_file = f"{slug}-001.jpg"
            # We'll set the path; actual upload is a separate step
            photo_path = f"ingredients/{slug}/photo.jpg"

            ing = Ingredient.objects.create(
                name=name,
                slug=slug,
                category=entry.get("category", ""),
                nutrition=entry.get("nutrition", {}),
                media={
                    "photo": photo_path,
                    "icon": None,
                    "illustration": None,
                },
                source="spoonacular",
                source_id=entry.get("id"),
                name_status="canonical",
            )

            # English translation
            IngredientTranslation.objects.create(
                ingredient=ing,
                locale="en",
                name=name,
                is_primary=True,
            )
            translation_count += 1
            created_count += 1

        self.stdout.write(f"  Spoonacular: {created_count} created, {skipped_count} skipped")

        # ── Phase 2: New EatPan-only ingredients ──
        self.stdout.write("\n--- Phase 2: EatPan-only ingredients ---")
        eatpan_created = 0
        new_eatpan = mapping.get("new_eatpan_ingredients", {})

        for ep_name, info in new_eatpan.items():
            name = info["name"]
            slug = info["slug"]

            # Skip if name OR slug already exists (e.g. "sun-dried-tomatoes" vs "sun dried tomatoes")
            if Ingredient.objects.filter(name=name).exists() or Ingredient.objects.filter(slug=slug).exists():
                skipped_count += 1
                continue

            photo_path = None
            if info.get("has_photo") and info.get("photo_file"):
                photo_path = f"ingredients/{slug}/photo.jpg"

            ing = Ingredient.objects.create(
                name=name,
                slug=slug,
                category=info.get("category", ""),
                media={
                    "photo": photo_path,
                    "icon": None,
                    "illustration": None,
                },
                source="eatpan",
                name_status="canonical",
            )

            IngredientTranslation.objects.create(
                ingredient=ing,
                locale="en",
                name=name,
                is_primary=True,
            )
            translation_count += 1
            eatpan_created += 1

        self.stdout.write(f"  EatPan-only: {eatpan_created} created")

        # ── Summary ──
        total = Ingredient.objects.count()
        self.stdout.write(f"\n=== DONE ===")
        self.stdout.write(f"Total ingredients in DB: {total}")
        self.stdout.write(f"Total translations: {translation_count}")
        self.stdout.write(self.style.SUCCESS(f"Successfully populated {total} ingredients"))
