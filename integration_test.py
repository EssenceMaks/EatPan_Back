import os
import sys
import django

# Setup Django env
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from rest_framework.test import APIClient
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from django.contrib.auth.models import User
from recipes.models import UserProfile

print("=== Starting Integration Tests for Phase 3-10 Endpoints ===")

# 1. Setup Users
user1, _ = User.objects.get_or_create(username='test_user_alpha')
user2, _ = User.objects.get_or_create(username='test_user_beta')

# Ensure profiles exist
UserProfile.objects.get_or_create(user=user1)
UserProfile.objects.get_or_create(user=user2)

client1 = APIClient()
client1.force_authenticate(user=user1)

client2 = APIClient()
client2.force_authenticate(user=user2)

errors = []

def test_endpoint(name, method, url, client, expected_status, data=None):
    if method == 'POST':
        resp = client.post(url, data, format='json')
    else:
        resp = client.get(url)
    
    if resp.status_code != expected_status:
        errors.append(f"[{name}] FAILED: Expected {expected_status}, got {resp.status_code}. Response: {resp.data}")
        return None
    print(f"[{name}] OK ({resp.status_code})")
    return resp.data

try:
    # --- PANTRY ---
    pantry_item = test_endpoint('Pantry Create User1', 'POST', '/api/v1/pantry/', client1, 201, {
        'name': 'Test Milk', 'quantity': 2, 'unit': 'liters'
    })
    test_endpoint('Pantry List User1', 'GET', '/api/v1/pantry/', client1, 200)
    user2_pantry = test_endpoint('Pantry Isolation User2', 'GET', '/api/v1/pantry/', client2, 200)
    if user2_pantry and len(user2_pantry) > 0 and any(i.get('name') == 'Test Milk' for i in user2_pantry):
        errors.append("[Pantry Isolation] FAILED: User2 can see User1's pantry item!")

    # --- SHOPPING ---
    shop_list = test_endpoint('Shopping Create User1', 'POST', '/api/v1/shopping/', client1, 201, {
        'title': 'Weekend Party'
    })
    test_endpoint('Shopping Item Add User1', 'POST', '/api/v1/shopping/items/', client1, 201, {
        'shopping_list_uuid': shop_list['uuid'] if shop_list else '',
        'name': 'Chips',
        'quantity': 5
    })

    # --- RECIPE (to test Meal Plan) ---
    recipe = test_endpoint('Recipe Create User1', 'POST', '/api/v1/recipes/', client1, 201, {
        'data': {'title': 'Test Cake'}
    })

    # --- MEAL PLAN ---
    if recipe:
        test_endpoint('Meal Plan Create User1', 'POST', '/api/v1/meal-plan/', client1, 201, {
            'recipe_uuid': recipe['uuid'],
            'scheduled_date': '2026-12-31T12:00:00Z',
            'meal_type': 'dinner'
        })

    # --- SOCIAL ---
    test_endpoint('Social Profile User1', 'GET', '/api/v1/social/me/', client1, 200)

except Exception as e:
    errors.append(f"Exception during testing: {str(e)}")

print("\n=== Test Results ===")
if errors:
    print("❌ SOME TESTS FAILED:")
    for err in errors:
        print("  -", err)
else:
    print("✅ ALL TESTS PASSED! Endpoints correctly process data and isolate users.")

# Cleanup
User.objects.filter(username__in=['test_user_alpha', 'test_user_beta']).delete()
print("Cleanup done.")
