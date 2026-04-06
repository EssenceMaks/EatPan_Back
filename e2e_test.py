import os
import sys
import time
import django

# Setup Django env
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from recipes.models import SyncOutbox, Recipe
from django.contrib.auth.models import User
from rest_framework.test import APIClient

print('=== 1. Creating Recipe via API (using internal Test Client) ===')
try:
    user, _ = User.objects.get_or_create(username='test_admin', is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=user)
    
    resp = client.post('/api/v1/recipes/', {'data': {'title': 'E2E Full Loop Auto-Test Recipe'}}, format='json')
    
    if resp.status_code != 201:
        print(f'Failed: HTTP {resp.status_code} - {resp.data}')
        sys.exit(1)
    
    recipe_uuid = resp.data['uuid']
    print(f'   Success! HTTP 201 Created. UUID: {recipe_uuid}')
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)

print('\n=== 2. Waiting 2s for NATS Daemons (Publisher & Consumer) ===')
time.sleep(2)

print('\n=== 3. Validating SyncOutbox (Database Queue) ===')
q = SyncOutbox.objects.filter(entity_uuid=recipe_uuid)
if q.exists():
    evt = q.first()
    print(f'   Event found! OP: "{evt.op}", Entity Type: "{evt.entity_type}"')
    if evt.published_at:
        print(f'   SUCCESS: Publisher picked it up and pushed to NATS at {evt.published_at}')
    else:
        print('   FAILED: Event exists but is NOT marked as published.')
else:
    print('   FAILED: No Outbox event was created by the API view.')

print('\n=== 4. Cleaning up Test Data ===')
Recipe.objects.filter(uuid=recipe_uuid).delete()
SyncOutbox.objects.filter(entity_uuid=recipe_uuid).delete()
print('   Cleanup done.')
