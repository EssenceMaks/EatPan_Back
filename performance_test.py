import os
import sys
import time
import django
import uuid

# Setup Django env
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from recipes.models import SyncOutbox, Recipe
from django.db import transaction

def run_performance_test():
    print("=== Запуск тесту продуктивності: Одиночні транзакції vs Пакетна (Batch) обробка ===\n")
    
    # Clean up before testing
    Recipe.objects.filter(data__title__contains="PerfTest").delete()
    SyncOutbox.objects.all().delete()
    
    count = 100
    
    # 1. Single inserts
    print(f"1. Створення {count} рецептів (по одному в циклі - Single)...")
    start_single = time.time()
    for i in range(count):
        Recipe.objects.create(data={"title": f"PerfTest Single {i}"})
    end_single = time.time()
    time_single_ms = int((end_single - start_single) * 1000)
    print(f"   Час виконання (Single): {time_single_ms} мс\n")
    
    # Clean up
    Recipe.objects.filter(data__title__contains="PerfTest").delete()
    SyncOutbox.objects.all().delete()
    
    # 2. Batch inserts
    print(f"2. Створення {count} рецептів (пакетно - Batch)...")
    recipes_to_create = [Recipe(uuid=uuid.uuid4(), data={"title": f"PerfTest Batch {i}"}) for i in range(count)]
    
    start_batch = time.time()
    with transaction.atomic():
        created_recipes = Recipe.objects.bulk_create(recipes_to_create)
        # У складних архітектурах події outbox також генеруються батчами
        outbox_items = [
            SyncOutbox(
                entity_type='recipe',
                entity_uuid=item.uuid,
                op='upsert',
                payload={},
                node_id='local'
            ) for item in created_recipes
        ]
        SyncOutbox.objects.bulk_create(outbox_items)
    end_batch = time.time()
    
    time_batch_ms = int((end_batch - start_batch) * 1000)
    print(f"   Час виконання (Batch): {time_batch_ms} мс\n")
    
    print("=== Результуючі показники ===")
    print(f"Одиночні: {time_single_ms} мс")
    print(f"Пакетні: {time_batch_ms} мс")
    print(f"Приріст швидкості: У {round(time_single_ms/time_batch_ms, 1)} разів швидше!\n")
    
    # Cleanup
    Recipe.objects.filter(data__title__contains="PerfTest").delete()
    SyncOutbox.objects.all().delete()

if __name__ == "__main__":
    run_performance_test()
