"""
Phase 4: Tasks Views
All task data is stored in UserProfile.tasks JSONB field.

Schema of UserProfile.tasks:
{
    "groups": {
        "<group_uuid>": {
            "name": "...", "color": "...", "icon": "...",
            "shared_with": ["<user_uuid>", ...],
            "created_at": "..."
        }
    },
    "items": {
        "<task_uuid>": {
            "title": "...", "description": "...",
            "group": "<group_uuid>",
            "status": "todo|in_progress|done",
            "priority": 1,
            "due_date": "...",
            "comments": [
                {"id": "<cid>", "author_uuid": "...", "text": "...", "created_at": "..."}
            ],
            "created_at": "...", "updated_at": "..."
        }
    }
}

Endpoints:
  GET    /tasks/                          — list all tasks
  POST   /tasks/                          — create task
  GET    /tasks/{task_uuid}/              — get single task
  PATCH  /tasks/{task_uuid}/              — edit task
  DELETE /tasks/{task_uuid}/              — delete task
  POST   /tasks/{task_uuid}/comments/     — add comment
  PATCH  /tasks/{task_uuid}/comments/{cid}/ — edit comment
  DELETE /tasks/{task_uuid}/comments/{cid}/ — delete comment
  GET    /task-groups/                    — list groups
  POST   /task-groups/                    — create group
  PATCH  /task-groups/{group_uuid}/       — edit group
  DELETE /task-groups/{group_uuid}/       — delete group
  POST   /task-groups/{group_uuid}/share/ — share group with user
"""
import uuid as uuid_mod
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile
from .sync_outbox import outbox_enqueue


def _get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.tasks, dict):
        profile.tasks = {'groups': {}, 'items': {}}
        profile.save(update_fields=['tasks'])
    if 'groups' not in profile.tasks:
        profile.tasks['groups'] = {}
    if 'items' not in profile.tasks:
        profile.tasks['items'] = {}
    return profile


def _sync_tasks(profile):
    profile.save(update_fields=['tasks', 'updated_at'])
    outbox_enqueue(
        entity_type='user_profile',
        entity_uuid=profile.uuid,
        op='patch',
        payload={'uuid': str(profile.uuid), 'tasks': profile.tasks},
    )


class TaskListView(APIView):
    """GET / POST /tasks/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request.user)
        items = profile.tasks.get('items', {})
        return Response({'items': items, 'count': len(items)})

    def post(self, request):
        profile = _get_profile(request.user)
        task_uuid = str(uuid_mod.uuid4())
        now = datetime.utcnow().isoformat()

        task = {
            'title': request.data.get('title', ''),
            'description': request.data.get('description', ''),
            'group': request.data.get('group', ''),
            'status': request.data.get('status', 'todo'),
            'priority': request.data.get('priority', 0),
            'due_date': request.data.get('due_date', ''),
            'comments': [],
            'created_at': now,
            'updated_at': now,
        }

        profile.tasks['items'][task_uuid] = task
        _sync_tasks(profile)
        return Response({'uuid': task_uuid, **task}, status=201)


class TaskDetailView(APIView):
    """GET / PATCH / DELETE /tasks/{task_uuid}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_uuid):
        profile = _get_profile(request.user)
        task = profile.tasks.get('items', {}).get(task_uuid)
        if not task:
            return Response({'error': 'Task not found'}, status=404)
        return Response({'uuid': task_uuid, **task})

    def patch(self, request, task_uuid):
        profile = _get_profile(request.user)
        task = profile.tasks.get('items', {}).get(task_uuid)
        if not task:
            return Response({'error': 'Task not found'}, status=404)

        for key in ['title', 'description', 'group', 'status', 'priority', 'due_date']:
            if key in request.data:
                task[key] = request.data[key]
        task['updated_at'] = datetime.utcnow().isoformat()

        profile.tasks['items'][task_uuid] = task
        _sync_tasks(profile)
        return Response({'uuid': task_uuid, **task})

    def delete(self, request, task_uuid):
        profile = _get_profile(request.user)
        if task_uuid in profile.tasks.get('items', {}):
            del profile.tasks['items'][task_uuid]
            _sync_tasks(profile)
        return Response(status=204)


class TaskCommentView(APIView):
    """POST /tasks/{task_uuid}/comments/
       PATCH/DELETE /tasks/{task_uuid}/comments/{cid}/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, task_uuid):
        profile = _get_profile(request.user)
        task = profile.tasks.get('items', {}).get(task_uuid)
        if not task:
            return Response({'error': 'Task not found'}, status=404)

        cid = str(uuid_mod.uuid4())
        comment = {
            'id': cid,
            'author_uuid': str(profile.uuid),
            'author_name': request.user.username,
            'text': request.data.get('text', ''),
            'created_at': datetime.utcnow().isoformat(),
        }

        if 'comments' not in task:
            task['comments'] = []
        task['comments'].append(comment)
        task['updated_at'] = datetime.utcnow().isoformat()

        profile.tasks['items'][task_uuid] = task
        _sync_tasks(profile)

        # If task is in a shared group, replicate comment to shared users
        group_uuid = task.get('group', '')
        if group_uuid:
            group = profile.tasks.get('groups', {}).get(group_uuid, {})
            shared_with = group.get('shared_with', [])
            for user_uuid in shared_with:
                try:
                    other_profile = UserProfile.objects.get(uuid=user_uuid)
                    other_tasks = other_profile.tasks or {}
                    other_items = other_tasks.get('items', {})
                    if task_uuid in other_items:
                        if 'comments' not in other_items[task_uuid]:
                            other_items[task_uuid]['comments'] = []
                        other_items[task_uuid]['comments'].append(comment)
                        other_items[task_uuid]['updated_at'] = datetime.utcnow().isoformat()
                        other_profile.save(update_fields=['tasks', 'updated_at'])
                except UserProfile.DoesNotExist:
                    pass

        return Response(comment, status=201)

    def patch(self, request, task_uuid, cid):
        profile = _get_profile(request.user)
        task = profile.tasks.get('items', {}).get(task_uuid)
        if not task:
            return Response({'error': 'Task not found'}, status=404)

        for comment in task.get('comments', []):
            if comment['id'] == cid:
                if 'text' in request.data:
                    comment['text'] = request.data['text']
                comment['edited_at'] = datetime.utcnow().isoformat()
                profile.tasks['items'][task_uuid] = task
                _sync_tasks(profile)
                return Response(comment)

        return Response({'error': 'Comment not found'}, status=404)

    def delete(self, request, task_uuid, cid):
        profile = _get_profile(request.user)
        task = profile.tasks.get('items', {}).get(task_uuid)
        if not task:
            return Response({'error': 'Task not found'}, status=404)

        task['comments'] = [c for c in task.get('comments', []) if c['id'] != cid]
        task['updated_at'] = datetime.utcnow().isoformat()
        profile.tasks['items'][task_uuid] = task
        _sync_tasks(profile)
        return Response(status=204)


class TaskGroupListView(APIView):
    """GET / POST /task-groups/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request.user)
        groups = profile.tasks.get('groups', {})
        return Response({'groups': groups, 'count': len(groups)})

    def post(self, request):
        profile = _get_profile(request.user)
        group_uuid = str(uuid_mod.uuid4())
        group = {
            'name': request.data.get('name', 'New Group'),
            'color': request.data.get('color', '#333'),
            'icon': request.data.get('icon', 'folder'),
            'shared_with': [],
            'created_at': datetime.utcnow().isoformat(),
        }
        profile.tasks['groups'][group_uuid] = group
        _sync_tasks(profile)
        return Response({'uuid': group_uuid, **group}, status=201)


class TaskGroupDetailView(APIView):
    """PATCH / DELETE /task-groups/{group_uuid}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_uuid):
        profile = _get_profile(request.user)
        group = profile.tasks.get('groups', {}).get(group_uuid)
        if not group:
            return Response({'error': 'Group not found'}, status=404)

        for key in ['name', 'color', 'icon']:
            if key in request.data:
                group[key] = request.data[key]

        profile.tasks['groups'][group_uuid] = group
        _sync_tasks(profile)
        return Response({'uuid': group_uuid, **group})

    def delete(self, request, group_uuid):
        profile = _get_profile(request.user)
        if group_uuid in profile.tasks.get('groups', {}):
            del profile.tasks['groups'][group_uuid]
            # Unassign tasks from this group
            for tid, task in profile.tasks.get('items', {}).items():
                if task.get('group') == group_uuid:
                    task['group'] = ''
            _sync_tasks(profile)
        return Response(status=204)


class TaskGroupShareView(APIView):
    """POST /task-groups/{group_uuid}/share/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, group_uuid):
        profile = _get_profile(request.user)
        group = profile.tasks.get('groups', {}).get(group_uuid)
        if not group:
            return Response({'error': 'Group not found'}, status=404)

        user_uuid = request.data.get('user_uuid', '')
        if not user_uuid:
            return Response({'error': 'user_uuid required'}, status=400)

        if user_uuid not in group.get('shared_with', []):
            group.setdefault('shared_with', []).append(user_uuid)

        profile.tasks['groups'][group_uuid] = group
        _sync_tasks(profile)

        # Copy group and its tasks to the other user
        try:
            other_profile = UserProfile.objects.get(uuid=user_uuid)
            other_tasks = other_profile.tasks or {'groups': {}, 'items': {}}
            if 'groups' not in other_tasks:
                other_tasks['groups'] = {}
            if 'items' not in other_tasks:
                other_tasks['items'] = {}

            other_tasks['groups'][group_uuid] = {
                **group,
                'owner_uuid': str(profile.uuid),
            }

            # Copy tasks belonging to this group
            for tid, task in profile.tasks.get('items', {}).items():
                if task.get('group') == group_uuid:
                    other_tasks['items'][tid] = task.copy()

            other_profile.tasks = other_tasks
            other_profile.save(update_fields=['tasks', 'updated_at'])
        except UserProfile.DoesNotExist:
            return Response({'error': 'Target user not found'}, status=404)

        return Response({'status': 'shared', 'group_uuid': group_uuid})
