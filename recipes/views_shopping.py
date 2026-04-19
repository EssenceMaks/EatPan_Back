"""
Phase 7: Shopping Views
All shopping data stored in UserProfile.shopping JSONB.

Schema of UserProfile.shopping:
{
    "lists": {
        "<list_uuid>": {
            "name": "Тижневий",
            "icon": "shopping-cart",
            "shared_with": ["<user_uuid>", ...],
            "items": {
                "<item_uuid>": {
                    "name": "Молоко",
                    "quantity": 2,
                    "unit": "л",
                    "category": "food_ingredient",
                    "purchased": false,
                    "price": null,
                    "notes": "",
                    "added_at": "..."
                }
            },
            "created_at": "...", "updated_at": "..."
        }
    }
}

Item categories: food_ingredient, food_other, cookware, household, other

Endpoints:
  GET    /shopping/                                   — all lists
  POST   /shopping/lists/                             — create list
  PATCH  /shopping/lists/{list_uuid}/                 — edit name, icon
  DELETE /shopping/lists/{list_uuid}/                 — delete list
  POST   /shopping/lists/{list_uuid}/share/           — share list
  POST   /shopping/lists/{list_uuid}/items/           — add item
  PATCH  /shopping/lists/{list_uuid}/items/{item_uuid}/ — edit item
  DELETE /shopping/lists/{list_uuid}/items/{item_uuid}/ — delete item
"""
import uuid as uuid_mod
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile
from .sync_outbox import outbox_enqueue


def _get_shopping(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.shopping, dict):
        profile.shopping = {'lists': {}}
        profile.save(update_fields=['shopping'])
    profile.shopping.setdefault('lists', {})
    return profile


def _sync_shopping(profile):
    profile.save(update_fields=['shopping', 'updated_at'])
    outbox_enqueue(
        entity_type='user_profile',
        entity_uuid=profile.uuid,
        op='patch',
        payload={'uuid': str(profile.uuid), 'shopping': profile.shopping},
    )


class ShoppingOverviewView(APIView):
    """GET /shopping/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_shopping(request.user)
        lists = profile.shopping.get('lists', {})
        # Return summary for each list
        summary = {}
        for lid, lst in lists.items():
            items = lst.get('items', {})
            purchased = sum(1 for i in items.values() if i.get('purchased'))
            summary[lid] = {
                'name': lst.get('name', ''),
                'icon': lst.get('icon', 'shopping-cart'),
                'total_items': len(items),
                'purchased': purchased,
                'remaining': len(items) - purchased,
                'shared_with': lst.get('shared_with', []),
            }
        return Response({'lists': summary, 'count': len(summary)})


class ShoppingListView(APIView):
    """POST /shopping/lists/
       PATCH/DELETE /shopping/lists/{list_uuid}/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_shopping(request.user)
        list_uuid = str(uuid_mod.uuid4())
        now = datetime.utcnow().isoformat()

        shopping_list = {
            'name': request.data.get('name', 'Shopping List'),
            'icon': request.data.get('icon', 'shopping-cart'),
            'shared_with': [],
            'items': {},
            'created_at': now,
            'updated_at': now,
        }

        profile.shopping['lists'][list_uuid] = shopping_list
        _sync_shopping(profile)
        return Response({'uuid': list_uuid, **shopping_list}, status=201)

    def patch(self, request, list_uuid=None):
        if not list_uuid:
            return Response({'error': 'list_uuid required'}, status=400)
        profile = _get_shopping(request.user)
        lst = profile.shopping.get('lists', {}).get(list_uuid)
        if not lst:
            return Response({'error': 'List not found'}, status=404)

        for key in ['name', 'icon']:
            if key in request.data:
                lst[key] = request.data[key]
        lst['updated_at'] = datetime.utcnow().isoformat()

        profile.shopping['lists'][list_uuid] = lst
        _sync_shopping(profile)
        return Response({'uuid': list_uuid, **lst})

    def delete(self, request, list_uuid=None):
        if not list_uuid:
            return Response({'error': 'list_uuid required'}, status=400)
        profile = _get_shopping(request.user)
        if list_uuid in profile.shopping.get('lists', {}):
            del profile.shopping['lists'][list_uuid]
            _sync_shopping(profile)
        return Response(status=204)


class ShoppingListShareView(APIView):
    """POST /shopping/lists/{list_uuid}/share/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, list_uuid):
        profile = _get_shopping(request.user)
        lst = profile.shopping.get('lists', {}).get(list_uuid)
        if not lst:
            return Response({'error': 'List not found'}, status=404)

        user_uuid = request.data.get('user_uuid', '')
        if not user_uuid:
            return Response({'error': 'user_uuid required'}, status=400)

        if user_uuid not in lst.get('shared_with', []):
            lst.setdefault('shared_with', []).append(user_uuid)

        profile.shopping['lists'][list_uuid] = lst
        _sync_shopping(profile)

        # Copy list to target user
        try:
            other_profile, _ = UserProfile.objects.get_or_create(
                uuid=user_uuid,
                defaults={'user_id': 1}  # placeholder
            )
            other_profile = UserProfile.objects.get(uuid=user_uuid)
            other_shopping = other_profile.shopping or {'lists': {}}
            other_shopping.setdefault('lists', {})
            other_shopping['lists'][list_uuid] = {
                **lst,
                'owner_uuid': str(profile.uuid),
            }
            other_profile.shopping = other_shopping
            other_profile.save(update_fields=['shopping', 'updated_at'])
        except UserProfile.DoesNotExist:
            return Response({'error': 'Target user not found'}, status=404)

        return Response({'status': 'shared', 'list_uuid': list_uuid})


class ShoppingItemView(APIView):
    """POST /shopping/lists/{list_uuid}/items/
       PATCH/DELETE /shopping/lists/{list_uuid}/items/{item_uuid}/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, list_uuid):
        profile = _get_shopping(request.user)
        lst = profile.shopping.get('lists', {}).get(list_uuid)
        if not lst:
            return Response({'error': 'List not found'}, status=404)

        item_uuid = str(uuid_mod.uuid4())
        item = {
            'name': request.data.get('name', ''),
            'quantity': request.data.get('quantity', 1),
            'unit': request.data.get('unit', 'шт'),
            'category': request.data.get('category', 'food_ingredient'),
            'purchased': False,
            'price': request.data.get('price'),
            'notes': request.data.get('notes', ''),
            'added_at': datetime.utcnow().isoformat(),
        }

        lst.setdefault('items', {})[item_uuid] = item
        lst['updated_at'] = datetime.utcnow().isoformat()
        profile.shopping['lists'][list_uuid] = lst
        _sync_shopping(profile)
        return Response({'uuid': item_uuid, **item}, status=201)

    def patch(self, request, list_uuid, item_uuid=None):
        if not item_uuid:
            return Response({'error': 'item_uuid required'}, status=400)
        profile = _get_shopping(request.user)
        lst = profile.shopping.get('lists', {}).get(list_uuid)
        if not lst:
            return Response({'error': 'List not found'}, status=404)
        item = lst.get('items', {}).get(item_uuid)
        if not item:
            return Response({'error': 'Item not found'}, status=404)

        for key in ['name', 'quantity', 'unit', 'category', 'purchased', 'price', 'notes']:
            if key in request.data:
                item[key] = request.data[key]

        lst['items'][item_uuid] = item
        lst['updated_at'] = datetime.utcnow().isoformat()
        profile.shopping['lists'][list_uuid] = lst
        _sync_shopping(profile)
        return Response({'uuid': item_uuid, **item})

    def delete(self, request, list_uuid, item_uuid=None):
        if not item_uuid:
            return Response({'error': 'item_uuid required'}, status=400)
        profile = _get_shopping(request.user)
        lst = profile.shopping.get('lists', {}).get(list_uuid)
        if not lst:
            return Response({'error': 'List not found'}, status=404)

        if item_uuid in lst.get('items', {}):
            del lst['items'][item_uuid]
            lst['updated_at'] = datetime.utcnow().isoformat()
            profile.shopping['lists'][list_uuid] = lst
            _sync_shopping(profile)
        return Response(status=204)
