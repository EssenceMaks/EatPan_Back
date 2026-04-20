"""
Phase 5: Meal Plan Views
All meal plan data is stored in UserProfile.meal_plan JSONB field.

Schema of UserProfile.meal_plan:
{
    "labels": {
        "<label_uuid>": {"name": "...", "color": "...", "icon": "..."}
    },
    "entries": {
        "<entry_uuid>": {
            "date": "2026-04-19",
            "meal_type": "breakfast|lunch|dinner|snack",
            "label": "<label_uuid>",
            "recipe_uuid": "...",
            "recipe_title": "...",
            "status": "planned|in_progress|done",
            "portions": 2,
            "notes": "...",
            "created_at": "...", "updated_at": "..."
        }
    }
}

Endpoints:
  GET    /meal-plan/                                — list all entries
  POST   /meal-plan/                                — create entry
  GET    /meal-plan/{entry_uuid}/                   — get entry
  PATCH  /meal-plan/{entry_uuid}/                   — edit status, time, etc.
  DELETE /meal-plan/{entry_uuid}/                   — delete entry
  POST   /meal-plan/{entry_uuid}/bind-recipe/       — bind recipe to entry
  DELETE /meal-plan/{entry_uuid}/unbind-recipe/{recipe_uuid}/ — unbind recipe
  GET    /meal-plan/labels/                         — list labels
  POST   /meal-plan/labels/                         — create label
  PATCH  /meal-plan/labels/{label_uuid}/            — edit label
  DELETE /meal-plan/labels/{label_uuid}/            — delete label
"""
import uuid as uuid_mod
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile, Recipe
from .sync_outbox import outbox_enqueue


def _get_meal_plan(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.meal_plan, dict):
        profile.meal_plan = {'labels': {}, 'entries': {}}
        profile.save(update_fields=['meal_plan'])
    profile.meal_plan.setdefault('labels', {})
    profile.meal_plan.setdefault('entries', {})
    return profile


def _sync_meal_plan(profile):
    profile.save(update_fields=['meal_plan', 'updated_at'])
    outbox_enqueue(
        entity_type='user_profile',
        entity_uuid=profile.uuid,
        op='patch',
        payload={'uuid': str(profile.uuid), 'meal_plan': profile.meal_plan},
    )


class MealPlanListView(APIView):
    """GET / POST /meal-plan/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_meal_plan(request.user)
        entries = profile.meal_plan.get('entries', {})
        # Filter by date range if provided
        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')
        if date_from or date_to:
            filtered = {}
            for uid, entry in entries.items():
                d = entry.get('date', '')
                if date_from and d < date_from:
                    continue
                if date_to and d > date_to:
                    continue
                filtered[uid] = entry
            return Response({'entries': filtered, 'count': len(filtered)})
        return Response({'entries': entries, 'count': len(entries)})

    def post(self, request):
        profile = _get_meal_plan(request.user)
        entry_uuid = str(uuid_mod.uuid4())
        now = datetime.utcnow().isoformat()

        entry = {
            'date': request.data.get('date', datetime.utcnow().strftime('%Y-%m-%d')),
            'meal_type': request.data.get('meal_type', 'lunch'),
            'label': request.data.get('label', ''),
            'recipe_uuid': request.data.get('recipe_uuid', ''),
            'recipe_title': request.data.get('recipe_title', ''),
            'status': request.data.get('status', 'planned'),
            'portions': request.data.get('portions', 1),
            'notes': request.data.get('notes', ''),
            'created_at': now,
            'updated_at': now,
        }

        profile.meal_plan['entries'][entry_uuid] = entry
        _sync_meal_plan(profile)
        return Response({'uuid': entry_uuid, **entry}, status=201)


class MealPlanDetailView(APIView):
    """GET / PATCH / DELETE /meal-plan/{entry_uuid}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, entry_uuid):
        profile = _get_meal_plan(request.user)
        entry = profile.meal_plan.get('entries', {}).get(entry_uuid)
        if not entry:
            return Response({'error': 'Entry not found'}, status=404)
        return Response({'uuid': entry_uuid, **entry})

    def patch(self, request, entry_uuid):
        profile = _get_meal_plan(request.user)
        entry = profile.meal_plan.get('entries', {}).get(entry_uuid)
        if not entry:
            return Response({'error': 'Entry not found'}, status=404)

        for key in ['date', 'meal_type', 'label', 'status', 'portions', 'notes',
                     'recipe_uuid', 'recipe_title']:
            if key in request.data:
                entry[key] = request.data[key]
        entry['updated_at'] = datetime.utcnow().isoformat()

        profile.meal_plan['entries'][entry_uuid] = entry
        _sync_meal_plan(profile)
        return Response({'uuid': entry_uuid, **entry})

    def delete(self, request, entry_uuid):
        profile = _get_meal_plan(request.user)
        if entry_uuid in profile.meal_plan.get('entries', {}):
            del profile.meal_plan['entries'][entry_uuid]
            _sync_meal_plan(profile)
        return Response(status=204)


class MealPlanBindRecipeView(APIView):
    """POST /meal-plan/{entry_uuid}/bind-recipe/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_uuid):
        profile = _get_meal_plan(request.user)
        entry = profile.meal_plan.get('entries', {}).get(entry_uuid)
        if not entry:
            return Response({'error': 'Entry not found'}, status=404)

        recipe_uuid = request.data.get('recipe_uuid')
        if not recipe_uuid:
            return Response({'error': 'recipe_uuid required'}, status=400)

        # Verify recipe exists
        try:
            recipe = Recipe.objects.get(uuid=recipe_uuid)
            entry['recipe_uuid'] = str(recipe.uuid)
            entry['recipe_title'] = recipe.data.get('title', '') if isinstance(recipe.data, dict) else ''
            entry['updated_at'] = datetime.utcnow().isoformat()

            profile.meal_plan['entries'][entry_uuid] = entry
            _sync_meal_plan(profile)
            return Response({'uuid': entry_uuid, **entry})
        except Recipe.DoesNotExist:
            return Response({'error': 'Recipe not found'}, status=404)


class MealPlanUnbindRecipeView(APIView):
    """DELETE /meal-plan/{entry_uuid}/unbind-recipe/{recipe_uuid}/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, entry_uuid, recipe_uuid):
        profile = _get_meal_plan(request.user)
        entry = profile.meal_plan.get('entries', {}).get(entry_uuid)
        if not entry:
            return Response({'error': 'Entry not found'}, status=404)

        if entry.get('recipe_uuid') == recipe_uuid:
            entry['recipe_uuid'] = ''
            entry['recipe_title'] = ''
            entry['updated_at'] = datetime.utcnow().isoformat()
            profile.meal_plan['entries'][entry_uuid] = entry
            _sync_meal_plan(profile)

        return Response(status=204)


class MealPlanLabelListView(APIView):
    """GET / POST /meal-plan/labels/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_meal_plan(request.user)
        labels = profile.meal_plan.get('labels', {})
        return Response({'labels': labels})

    def post(self, request):
        profile = _get_meal_plan(request.user)
        label_uuid = str(uuid_mod.uuid4())
        label = {
            'name': request.data.get('name', 'Label'),
            'color': request.data.get('color', '#888'),
            'icon': request.data.get('icon', 'tag'),
            'inStock': request.data.get('inStock', True),
            'recipe_uuid': request.data.get('recipe_uuid', ''),
            'location_uuid': request.data.get('location_uuid', ''),
        }
        profile.meal_plan['labels'][label_uuid] = label
        _sync_meal_plan(profile)
        return Response({'uuid': label_uuid, **label}, status=201)


class MealPlanLabelDetailView(APIView):
    """PATCH / DELETE /meal-plan/labels/{label_uuid}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, label_uuid):
        profile = _get_meal_plan(request.user)
        label = profile.meal_plan.get('labels', {}).get(label_uuid)
        if not label:
            return Response({'error': 'Label not found'}, status=404)

        for key in ['name', 'color', 'icon', 'inStock', 'recipe_uuid', 'location_uuid']:
            if key in request.data:
                label[key] = request.data[key]

        profile.meal_plan['labels'][label_uuid] = label
        _sync_meal_plan(profile)
        return Response({'uuid': label_uuid, **label})

    def delete(self, request, label_uuid):
        profile = _get_meal_plan(request.user)
        if label_uuid in profile.meal_plan.get('labels', {}):
            del profile.meal_plan['labels'][label_uuid]
            # Remove label from entries
            for eid, entry in profile.meal_plan.get('entries', {}).items():
                if entry.get('label') == label_uuid:
                    entry['label'] = ''
            _sync_meal_plan(profile)
        return Response(status=204)

class MealPlanLocationListView(APIView):
    """GET / POST /meal-plan/locations/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_meal_plan(request.user)
        locations = profile.meal_plan.get('locations', {})
        return Response({'locations': locations})

    def post(self, request):
        profile = _get_meal_plan(request.user)
        if 'locations' not in profile.meal_plan:
            profile.meal_plan['locations'] = {}
        
        loc_uuid = str(uuid_mod.uuid4())
        loc = {
            'name': request.data.get('name', 'Location'),
        }
        profile.meal_plan['locations'][loc_uuid] = loc
        _sync_meal_plan(profile)
        return Response({'uuid': loc_uuid, **loc}, status=201)

class MealPlanLocationDetailView(APIView):
    """PATCH / DELETE /meal-plan/locations/{loc_uuid}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, loc_uuid):
        profile = _get_meal_plan(request.user)
        loc = profile.meal_plan.get('locations', {}).get(loc_uuid)
        if not loc:
            return Response({'error': 'Location not found'}, status=404)
        
        if 'name' in request.data:
            loc['name'] = request.data['name']
            
        profile.meal_plan['locations'][loc_uuid] = loc
        _sync_meal_plan(profile)
        return Response({'uuid': loc_uuid, **loc})

    def delete(self, request, loc_uuid):
        profile = _get_meal_plan(request.user)
        if loc_uuid in profile.meal_plan.get('locations', {}):
            del profile.meal_plan['locations'][loc_uuid]
            
            # Unlink this location from any labels
            for label_uuid, label in profile.meal_plan.get('labels', {}).items():
                if label.get('location_uuid') == loc_uuid:
                    label['location_uuid'] = ''
                    
            _sync_meal_plan(profile)
        return Response(status=204)
