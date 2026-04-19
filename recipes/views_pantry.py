"""
Phase 6: Pantry Views
All pantry data stored in UserProfile.pantry JSONB.

Schema of UserProfile.pantry:
{
    "locations": {
        "<loc_uuid>": {"name": "Холодильник", "icon": "refrigerator", "color": "#3388ff"}
    },
    "items": {
        "<item_uuid>": {
            "name": "Молоко",
            "quantity": 2,
            "unit": "л",
            "location": "<loc_uuid>",
            "category": "food_ingredient",
            "media_uuid": "...",
            "purchase_date": "2026-04-15",
            "expiration_date": "2026-04-25",
            "notes": "...",
            "created_at": "...", "updated_at": "..."
        }
    }
}

Endpoints:
  GET    /pantry/                         — list all items
  POST   /pantry/items/                   — add item
  PATCH  /pantry/items/{item_uuid}/       — edit quantity, expiration, location
  DELETE /pantry/items/{item_uuid}/       — remove item
  GET    /pantry/locations/               — list locations
  POST   /pantry/locations/               — create location
  PATCH  /pantry/locations/{loc_uuid}/    — edit location
  DELETE /pantry/locations/{loc_uuid}/    — delete location
  GET    /pantry/expiration-report/       — freshness report
"""
import uuid as uuid_mod
from datetime import datetime, date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile
from .sync_outbox import outbox_enqueue


def _get_pantry(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.pantry, dict):
        profile.pantry = {'locations': {}, 'items': {}}
        profile.save(update_fields=['pantry'])
    profile.pantry.setdefault('locations', {})
    profile.pantry.setdefault('items', {})
    return profile


def _sync_pantry(profile):
    profile.save(update_fields=['pantry', 'updated_at'])
    outbox_enqueue(
        entity_type='user_profile',
        entity_uuid=profile.uuid,
        op='patch',
        payload={'uuid': str(profile.uuid), 'pantry': profile.pantry},
    )


class PantryListView(APIView):
    """GET /pantry/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_pantry(request.user)
        items = profile.pantry.get('items', {})
        locations = profile.pantry.get('locations', {})
        return Response({
            'items': items,
            'locations': locations,
            'item_count': len(items),
        })


class PantryItemView(APIView):
    """POST /pantry/items/
       PATCH/DELETE /pantry/items/{item_uuid}/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_pantry(request.user)
        item_uuid = str(uuid_mod.uuid4())
        now = datetime.utcnow().isoformat()

        item = {
            'name': request.data.get('name', ''),
            'quantity': request.data.get('quantity', 1),
            'unit': request.data.get('unit', 'шт'),
            'location': request.data.get('location', ''),
            'category': request.data.get('category', 'food_ingredient'),
            'media_uuid': request.data.get('media_uuid', ''),
            'purchase_date': request.data.get('purchase_date', ''),
            'expiration_date': request.data.get('expiration_date', ''),
            'notes': request.data.get('notes', ''),
            'created_at': now,
            'updated_at': now,
        }

        profile.pantry['items'][item_uuid] = item
        _sync_pantry(profile)
        return Response({'uuid': item_uuid, **item}, status=201)

    def patch(self, request, item_uuid=None):
        if not item_uuid:
            return Response({'error': 'item_uuid required'}, status=400)
        profile = _get_pantry(request.user)
        item = profile.pantry.get('items', {}).get(item_uuid)
        if not item:
            return Response({'error': 'Item not found'}, status=404)

        for key in ['name', 'quantity', 'unit', 'location', 'category',
                     'media_uuid', 'purchase_date', 'expiration_date', 'notes']:
            if key in request.data:
                item[key] = request.data[key]
        item['updated_at'] = datetime.utcnow().isoformat()

        profile.pantry['items'][item_uuid] = item
        _sync_pantry(profile)
        return Response({'uuid': item_uuid, **item})

    def delete(self, request, item_uuid=None):
        if not item_uuid:
            return Response({'error': 'item_uuid required'}, status=400)
        profile = _get_pantry(request.user)
        if item_uuid in profile.pantry.get('items', {}):
            del profile.pantry['items'][item_uuid]
            _sync_pantry(profile)
        return Response(status=204)


class PantryLocationView(APIView):
    """GET/POST /pantry/locations/
       PATCH/DELETE /pantry/locations/{loc_uuid}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_pantry(request.user)
        return Response({'locations': profile.pantry.get('locations', {})})

    def post(self, request):
        profile = _get_pantry(request.user)
        loc_uuid = str(uuid_mod.uuid4())
        loc = {
            'name': request.data.get('name', 'Location'),
            'icon': request.data.get('icon', 'box'),
            'color': request.data.get('color', '#666'),
        }
        profile.pantry['locations'][loc_uuid] = loc
        _sync_pantry(profile)
        return Response({'uuid': loc_uuid, **loc}, status=201)

    def patch(self, request, loc_uuid=None):
        if not loc_uuid:
            return Response({'error': 'loc_uuid required'}, status=400)
        profile = _get_pantry(request.user)
        loc = profile.pantry.get('locations', {}).get(loc_uuid)
        if not loc:
            return Response({'error': 'Location not found'}, status=404)

        for key in ['name', 'icon', 'color']:
            if key in request.data:
                loc[key] = request.data[key]

        profile.pantry['locations'][loc_uuid] = loc
        _sync_pantry(profile)
        return Response({'uuid': loc_uuid, **loc})

    def delete(self, request, loc_uuid=None):
        if not loc_uuid:
            return Response({'error': 'loc_uuid required'}, status=400)
        profile = _get_pantry(request.user)
        if loc_uuid in profile.pantry.get('locations', {}):
            del profile.pantry['locations'][loc_uuid]
            # Unlink items from this location
            for iid, item in profile.pantry.get('items', {}).items():
                if item.get('location') == loc_uuid:
                    item['location'] = ''
            _sync_pantry(profile)
        return Response(status=204)


class PantryExpirationReportView(APIView):
    """GET /pantry/expiration-report/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_pantry(request.user)
        items = profile.pantry.get('items', {})
        today = date.today().isoformat()

        report = {
            'expired': [],
            'expiring_soon': [],  # within 3 days
            'fresh': [],
            'no_date': [],
        }

        for uid, item in items.items():
            exp = item.get('expiration_date', '')
            entry = {'uuid': uid, **item}
            if not exp:
                report['no_date'].append(entry)
            elif exp < today:
                report['expired'].append(entry)
            elif exp <= (datetime.utcnow().strftime('%Y-%m-%d')):
                report['expiring_soon'].append(entry)
            else:
                # Check if expiring within 3 days
                try:
                    exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
                    days_left = (exp_date - date.today()).days
                    entry['days_left'] = days_left
                    if days_left <= 3:
                        report['expiring_soon'].append(entry)
                    else:
                        report['fresh'].append(entry)
                except (ValueError, TypeError):
                    report['no_date'].append(entry)

        return Response(report)
