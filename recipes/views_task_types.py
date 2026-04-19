"""
Phase 14: Task Types & Subtypes CRUD
Stored in UserProfile.user_data['task_types'] JSONB field.

Schema:
{
    "task_types": {
        "<type_uuid>": {
            "name": "Покупки", "slug": "shopping",
            "icon": "shopping-cart", "color": "#f59e0b",
            "is_system": true, "order": 5,
            "subtypes": {
                "<subtype_uuid>": {
                    "name": "Закупка", "slug": "shop_big",
                    "icon": "shopping-cart", "color": "",
                    "defaults": {
                        "action_min": 60, "effect_min": 60,
                        "energy_start": 60, "energy_end": 40,
                        "mental_cost_pct": 20, "physical_cost_pct": 40
                    },
                    "is_system": true, "order": 0
                }
            }
        }
    }
}

Endpoints:
  GET    /task-types/                              — list all types + subtypes
  POST   /task-types/                              — create type
  PATCH  /task-types/{type_uuid}/                   — edit type
  DELETE /task-types/{type_uuid}/                   — delete (only !is_system)
  POST   /task-types/{type_uuid}/subtypes/          — add subtype
  PATCH  /task-subtypes/{subtype_uuid}/             — edit subtype
  DELETE /task-subtypes/{subtype_uuid}/             — delete subtype
"""
import uuid as uuid_mod
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile


# ============================================================
# System seed data — 15 types from reference preset2
# ============================================================
SYSTEM_TYPES = {
    'main': {
        'name': 'Основні', 'slug': 'main', 'icon': 'layout-grid', 'color': '#94a3b8',
        'is_system': True, 'order': 0,
        'subtypes': {
            'sleep':   {'name': 'Сон',          'slug': 'sleep',   'icon': 'moon',       'color': '#3b82f6', 'defaults': {'action_min': 480, 'effect_min': 480, 'energy_start': 15, 'energy_end': 85, 'mental_cost_pct': 0, 'physical_cost_pct': 0}, 'is_system': True, 'order': 0},
            'food':    {'name': 'Прийом їжі',   'slug': 'food',    'icon': 'utensils',   'color': '#10b981', 'defaults': {'action_min': 20,  'effect_min': 300, 'energy_start': 40, 'energy_end': 65, 'mental_cost_pct': 5, 'physical_cost_pct': 5}, 'is_system': True, 'order': 1},
            'train':   {'name': 'Тренування',   'slug': 'train',   'icon': 'dumbbell',   'color': '#f43f5e', 'defaults': {'action_min': 20,  'effect_min': 120, 'energy_start': 70, 'energy_end': 40, 'mental_cost_pct': 10, 'physical_cost_pct': 70}, 'is_system': True, 'order': 2},
            'prep':    {'name': 'Готування',     'slug': 'prep',    'icon': 'chef-hat',   'color': '#8b5cf6', 'defaults': {'action_min': 45,  'effect_min': 45,  'energy_start': 60, 'energy_end': 55, 'mental_cost_pct': 20, 'physical_cost_pct': 30}, 'is_system': True, 'order': 3},
            'ticket':  {'name': 'Тікет',         'slug': 'ticket',  'icon': 'ticket',     'color': '#06b6d4', 'defaults': {'action_min': 60,  'effect_min': 60,  'energy_start': 60, 'energy_end': 50, 'mental_cost_pct': 40, 'physical_cost_pct': 10}, 'is_system': True, 'order': 4},
            'work':    {'name': 'Робота',        'slug': 'work',    'icon': 'briefcase',  'color': '#6366f1', 'defaults': {'action_min': 240, 'effect_min': 120, 'energy_start': 80, 'energy_end': 30, 'mental_cost_pct': 70, 'physical_cost_pct': 20}, 'is_system': True, 'order': 5},
            'laundry': {'name': 'Прання',        'slug': 'laundry', 'icon': 'shirt',      'color': '#a855f7', 'defaults': {'action_min': 15,  'effect_min': 120, 'energy_start': 50, 'energy_end': 45, 'mental_cost_pct': 5, 'physical_cost_pct': 15}, 'is_system': True, 'order': 6},
        }
    },
    'health': {
        'name': "Здоров'я", 'slug': 'health', 'icon': 'pill', 'color': '#14b8a6',
        'is_system': True, 'order': 1,
        'subtypes': {
            'vit_bads':  {'name': 'Вітаміни', 'slug': 'vit_bads',  'icon': 'pill',     'color': '#14b8a6', 'defaults': {'action_min': 5,  'effect_min': 60,  'energy_start': 50, 'energy_end': 55, 'mental_cost_pct': 0, 'physical_cost_pct': 0}, 'is_system': True, 'order': 0},
            'first_aid': {'name': 'Аптечка',  'slug': 'first_aid', 'icon': 'activity', 'color': '#14b8a6', 'defaults': {'action_min': 5,  'effect_min': 120, 'energy_start': 30, 'energy_end': 40, 'mental_cost_pct': 5, 'physical_cost_pct': 5}, 'is_system': True, 'order': 1},
        }
    },
    'shopping': {
        'name': 'Покупки', 'slug': 'shopping', 'icon': 'shopping-cart', 'color': '#f59e0b',
        'is_system': True, 'order': 2,
        'subtypes': {
            'shop_big':      {'name': 'Закупка',  'slug': 'shop_big',      'icon': 'shopping-cart', 'color': '#f59e0b', 'defaults': {'action_min': 60,  'effect_min': 60,  'energy_start': 60, 'energy_end': 40, 'mental_cost_pct': 15, 'physical_cost_pct': 40}, 'is_system': True, 'order': 0},
            'shop_small':    {'name': 'Магазин',  'slug': 'shop_small',    'icon': 'shopping-bag',  'color': '#f59e0b', 'defaults': {'action_min': 20,  'effect_min': 20,  'energy_start': 55, 'energy_end': 45, 'mental_cost_pct': 10, 'physical_cost_pct': 20}, 'is_system': True, 'order': 1},
            'shop_delivery': {'name': 'Доставка', 'slug': 'shop_delivery', 'icon': 'truck',         'color': '#f59e0b', 'defaults': {'action_min': 10,  'effect_min': 10,  'energy_start': 50, 'energy_end': 50, 'mental_cost_pct': 5, 'physical_cost_pct': 0}, 'is_system': True, 'order': 2},
            'shop_clothes':  {'name': 'Одяг',     'slug': 'shop_clothes',  'icon': 'shirt',         'color': '#f59e0b', 'defaults': {'action_min': 120, 'effect_min': 60,  'energy_start': 80, 'energy_end': 50, 'mental_cost_pct': 30, 'physical_cost_pct': 30}, 'is_system': True, 'order': 3},
        }
    },
    'leisure': {
        'name': 'Відпочинок', 'slug': 'leisure', 'icon': 'party-popper', 'color': '#ec4899',
        'is_system': True, 'order': 3,
        'subtypes': {
            'party_cafe':  {'name': 'Кафе',  'slug': 'party_cafe',  'icon': 'coffee',   'color': '#ec4899', 'defaults': {'action_min': 120, 'effect_min': 180, 'energy_start': 60, 'energy_end': 80, 'mental_cost_pct': 0, 'physical_cost_pct': 5}, 'is_system': True, 'order': 0},
            'party_beach': {'name': 'Пляж',  'slug': 'party_beach', 'icon': 'umbrella', 'color': '#ec4899', 'defaults': {'action_min': 240, 'effect_min': 360, 'energy_start': 80, 'energy_end': 90, 'mental_cost_pct': 0, 'physical_cost_pct': 10}, 'is_system': True, 'order': 1},
        }
    },
}


def _get_types_store(user):
    """Get task_types from UserProfile.user_data, seeding system types if empty."""
    from .models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.user_data, dict):
        profile.user_data = {}
    if 'task_types' not in profile.user_data:
        # Seed system types on first access
        seeded = {}
        for key, t in SYSTEM_TYPES.items():
            type_uuid = str(uuid_mod.uuid4())
            subtypes_seeded = {}
            for sk, sv in t.get('subtypes', {}).items():
                sub_uuid = str(uuid_mod.uuid4())
                subtypes_seeded[sub_uuid] = sv
            seeded[type_uuid] = {
                'name': t['name'], 'slug': t['slug'], 'icon': t['icon'],
                'color': t['color'], 'is_system': t['is_system'], 'order': t['order'],
                'subtypes': subtypes_seeded,
            }
        profile.user_data['task_types'] = seeded
        profile.save(update_fields=['user_data'])
    return profile


class TaskTypeListView(APIView):
    """GET / POST /task-types/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_types_store(request.user)
        types = profile.user_data.get('task_types', {})
        result = []
        for uid, t in sorted(types.items(), key=lambda x: x[1].get('order', 99)):
            subtypes = []
            for sid, s in sorted(t.get('subtypes', {}).items(), key=lambda x: x[1].get('order', 99)):
                subtypes.append({'uuid': sid, **s})
            result.append({'uuid': uid, **{k: v for k, v in t.items() if k != 'subtypes'}, 'subtypes': subtypes})
        return Response({'types': result})

    def post(self, request):
        profile = _get_types_store(request.user)
        type_uuid = str(uuid_mod.uuid4())
        new_type = {
            'name': request.data.get('name', 'New Type'),
            'slug': request.data.get('slug', ''),
            'icon': request.data.get('icon', 'circle'),
            'color': request.data.get('color', '#888888'),
            'is_system': False,
            'order': request.data.get('order', 99),
            'subtypes': {},
        }
        profile.user_data['task_types'][type_uuid] = new_type
        profile.save(update_fields=['user_data'])
        return Response({'uuid': type_uuid, **new_type}, status=201)


class TaskTypeDetailView(APIView):
    """PATCH / DELETE /task-types/{type_uuid}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, type_uuid):
        profile = _get_types_store(request.user)
        t = profile.user_data.get('task_types', {}).get(type_uuid)
        if not t:
            return Response({'error': 'Type not found'}, status=404)
        for key in ['name', 'slug', 'icon', 'color', 'order']:
            if key in request.data:
                t[key] = request.data[key]
        profile.user_data['task_types'][type_uuid] = t
        profile.save(update_fields=['user_data'])
        return Response({'uuid': type_uuid, **t})

    def delete(self, request, type_uuid):
        profile = _get_types_store(request.user)
        t = profile.user_data.get('task_types', {}).get(type_uuid)
        if not t:
            return Response({'error': 'Type not found'}, status=404)
        if t.get('is_system'):
            return Response({'error': 'Cannot delete system type'}, status=403)
        del profile.user_data['task_types'][type_uuid]
        profile.save(update_fields=['user_data'])
        return Response(status=204)


class TaskSubtypeCreateView(APIView):
    """POST /task-types/{type_uuid}/subtypes/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, type_uuid):
        profile = _get_types_store(request.user)
        t = profile.user_data.get('task_types', {}).get(type_uuid)
        if not t:
            return Response({'error': 'Type not found'}, status=404)
        sub_uuid = str(uuid_mod.uuid4())
        new_sub = {
            'name': request.data.get('name', 'New Subtype'),
            'slug': request.data.get('slug', ''),
            'icon': request.data.get('icon', t.get('icon', 'circle')),
            'color': request.data.get('color', ''),
            'defaults': request.data.get('defaults', {
                'action_min': 60, 'effect_min': 60,
                'energy_start': 50, 'energy_end': 50,
                'mental_cost_pct': 0, 'physical_cost_pct': 0,
            }),
            'is_system': False,
            'order': request.data.get('order', 99),
        }
        if 'subtypes' not in t:
            t['subtypes'] = {}
        t['subtypes'][sub_uuid] = new_sub
        profile.user_data['task_types'][type_uuid] = t
        profile.save(update_fields=['user_data'])
        return Response({'uuid': sub_uuid, 'parent_uuid': type_uuid, **new_sub}, status=201)


class TaskSubtypeDetailView(APIView):
    """PATCH / DELETE /task-subtypes/{subtype_uuid}/"""
    permission_classes = [IsAuthenticated]

    def _find_subtype(self, profile, subtype_uuid):
        for tid, t in profile.user_data.get('task_types', {}).items():
            for sid, s in t.get('subtypes', {}).items():
                if sid == subtype_uuid:
                    return tid, sid, s
        return None, None, None

    def patch(self, request, subtype_uuid):
        profile = _get_types_store(request.user)
        tid, sid, sub = self._find_subtype(profile, subtype_uuid)
        if not sub:
            return Response({'error': 'Subtype not found'}, status=404)
        for key in ['name', 'slug', 'icon', 'color', 'order', 'defaults']:
            if key in request.data:
                sub[key] = request.data[key]
        profile.user_data['task_types'][tid]['subtypes'][sid] = sub
        profile.save(update_fields=['user_data'])
        return Response({'uuid': sid, 'parent_uuid': tid, **sub})

    def delete(self, request, subtype_uuid):
        profile = _get_types_store(request.user)
        tid, sid, sub = self._find_subtype(profile, subtype_uuid)
        if not sub:
            return Response({'error': 'Subtype not found'}, status=404)
        if sub.get('is_system'):
            return Response({'error': 'Cannot delete system subtype'}, status=403)
        del profile.user_data['task_types'][tid]['subtypes'][sid]
        profile.save(update_fields=['user_data'])
        return Response(status=204)
