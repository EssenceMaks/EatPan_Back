"""
Phase 8: Social Views
All social data stored in UserProfile.social JSONB.

Schema of UserProfile.social:
{
    "friends": {
        "<user_uuid>": {
            "status": "pending|accepted|blocked",
            "group": "<group_uuid>",
            "nickname": "...",
            "added_at": "..."
        }
    },
    "friend_groups": {
        "<group_uuid>": {
            "name": "Друзі",
            "color": "#3388ff",
            "permissions": {
                "show_meal_plan": true,
                "show_pantry": false,
                "show_shopping": false,
                "show_recipes": true
            }
        }
    },
    "followers": ["<user_uuid>", ...],
    "following": ["<user_uuid>", ...]
}

Endpoints:
  POST   /social/follow/{target_uuid}/              — follow user
  DELETE /social/follow/{target_uuid}/              — unfollow user
  POST   /social/friends/{target_uuid}/             — send friend request
  PATCH  /social/friends/{target_uuid}/             — accept/block/update friend
  DELETE /social/friends/{target_uuid}/             — remove friend
  GET    /social/friend-groups/                     — list groups
  POST   /social/friend-groups/                     — create group
  PATCH  /social/friend-groups/{group_uuid}/        — edit group
  DELETE /social/friend-groups/{group_uuid}/        — delete group
  GET    /social/followers/                         — list followers
  GET    /social/following/                         — list following
"""
import uuid as uuid_mod
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile
from .sync_outbox import outbox_enqueue


def _get_social(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.social, dict):
        profile.social = {'friends': {}, 'friend_groups': {}, 'followers': [], 'following': []}
        profile.save(update_fields=['social'])
    profile.social.setdefault('friends', {})
    profile.social.setdefault('friend_groups', {})
    profile.social.setdefault('followers', [])
    profile.social.setdefault('following', [])
    return profile


def _sync_social(profile):
    profile.save(update_fields=['social', 'updated_at'])
    outbox_enqueue(
        entity_type='user_profile',
        entity_uuid=profile.uuid,
        op='patch',
        payload={'uuid': str(profile.uuid), 'social': profile.social},
    )


class FollowView(APIView):
    """POST/DELETE /social/follow/{target_uuid}/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, target_uuid):
        """Follow a user"""
        profile = _get_social(request.user)

        if str(profile.uuid) == target_uuid:
            return Response({'error': 'Cannot follow yourself'}, status=400)

        following = profile.social.get('following', [])
        if target_uuid not in following:
            following.append(target_uuid)
            profile.social['following'] = following
            _sync_social(profile)

            # Add me to target's followers
            try:
                target_profile = UserProfile.objects.get(uuid=target_uuid)
                target_social = target_profile.social or {'followers': []}
                target_social.setdefault('followers', [])
                my_uuid = str(profile.uuid)
                if my_uuid not in target_social['followers']:
                    target_social['followers'].append(my_uuid)
                    target_profile.social = target_social
                    target_profile.save(update_fields=['social', 'updated_at'])
            except UserProfile.DoesNotExist:
                pass

        return Response({'status': 'following', 'target': target_uuid})

    def delete(self, request, target_uuid):
        """Unfollow a user"""
        profile = _get_social(request.user)
        following = profile.social.get('following', [])
        if target_uuid in following:
            following.remove(target_uuid)
            profile.social['following'] = following
            _sync_social(profile)

            # Remove me from target's followers
            try:
                target_profile = UserProfile.objects.get(uuid=target_uuid)
                target_social = target_profile.social or {}
                followers = target_social.get('followers', [])
                my_uuid = str(profile.uuid)
                if my_uuid in followers:
                    followers.remove(my_uuid)
                    target_profile.social = target_social
                    target_profile.save(update_fields=['social', 'updated_at'])
            except UserProfile.DoesNotExist:
                pass

        return Response(status=204)


class FriendView(APIView):
    """POST/PATCH/DELETE /social/friends/{target_uuid}/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, target_uuid):
        """Send friend request"""
        profile = _get_social(request.user)

        if str(profile.uuid) == target_uuid:
            return Response({'error': 'Cannot add yourself'}, status=400)

        friends = profile.social.get('friends', {})
        if target_uuid in friends:
            return Response({'error': 'Friend entry already exists', 'status': friends[target_uuid].get('status')}, status=400)

        friends[target_uuid] = {
            'status': 'pending',
            'group': '',
            'nickname': request.data.get('nickname', ''),
            'added_at': datetime.utcnow().isoformat(),
        }
        profile.social['friends'] = friends
        _sync_social(profile)

        # Add pending request to target's profile
        try:
            target_profile = UserProfile.objects.get(uuid=target_uuid)
            target_social = target_profile.social or {'friends': {}}
            target_social.setdefault('friends', {})
            my_uuid = str(profile.uuid)
            target_social['friends'][my_uuid] = {
                'status': 'pending',
                'group': '',
                'nickname': '',
                'added_at': datetime.utcnow().isoformat(),
            }
            target_profile.social = target_social
            target_profile.save(update_fields=['social', 'updated_at'])
        except UserProfile.DoesNotExist:
            pass

        return Response({'status': 'pending', 'target': target_uuid}, status=201)

    def patch(self, request, target_uuid):
        """Accept, block, or update friend entry"""
        profile = _get_social(request.user)
        friends = profile.social.get('friends', {})
        if target_uuid not in friends:
            return Response({'error': 'Friend not found'}, status=404)

        friend = friends[target_uuid]
        new_status = request.data.get('status')
        if new_status in ('accepted', 'blocked', 'pending'):
            friend['status'] = new_status

        if 'group' in request.data:
            friend['group'] = request.data['group']
        if 'nickname' in request.data:
            friend['nickname'] = request.data['nickname']

        friends[target_uuid] = friend
        profile.social['friends'] = friends
        _sync_social(profile)

        # If accepting, update target's entry to accepted as well
        if new_status == 'accepted':
            try:
                target_profile = UserProfile.objects.get(uuid=target_uuid)
                target_social = target_profile.social or {'friends': {}}
                my_uuid = str(profile.uuid)
                if my_uuid in target_social.get('friends', {}):
                    target_social['friends'][my_uuid]['status'] = 'accepted'
                    target_profile.social = target_social
                    target_profile.save(update_fields=['social', 'updated_at'])
            except UserProfile.DoesNotExist:
                pass

        return Response({'target': target_uuid, **friend})

    def delete(self, request, target_uuid):
        """Remove friend"""
        profile = _get_social(request.user)
        friends = profile.social.get('friends', {})
        if target_uuid in friends:
            del friends[target_uuid]
            profile.social['friends'] = friends
            _sync_social(profile)

            # Remove from target
            try:
                target_profile = UserProfile.objects.get(uuid=target_uuid)
                target_social = target_profile.social or {}
                my_uuid = str(profile.uuid)
                if my_uuid in target_social.get('friends', {}):
                    del target_social['friends'][my_uuid]
                    target_profile.social = target_social
                    target_profile.save(update_fields=['social', 'updated_at'])
            except UserProfile.DoesNotExist:
                pass

        return Response(status=204)


class FriendGroupListView(APIView):
    """GET / POST /social/friend-groups/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_social(request.user)
        groups = profile.social.get('friend_groups', {})
        return Response({'groups': groups})

    def post(self, request):
        profile = _get_social(request.user)
        group_uuid = str(uuid_mod.uuid4())
        group = {
            'name': request.data.get('name', 'Friends'),
            'color': request.data.get('color', '#3388ff'),
            'permissions': request.data.get('permissions', {
                'show_meal_plan': False,
                'show_pantry': False,
                'show_shopping': False,
                'show_recipes': True,
            }),
        }
        profile.social['friend_groups'][group_uuid] = group
        _sync_social(profile)
        return Response({'uuid': group_uuid, **group}, status=201)


class FriendGroupDetailView(APIView):
    """PATCH / DELETE /social/friend-groups/{group_uuid}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_uuid):
        profile = _get_social(request.user)
        group = profile.social.get('friend_groups', {}).get(group_uuid)
        if not group:
            return Response({'error': 'Group not found'}, status=404)

        for key in ['name', 'color', 'permissions']:
            if key in request.data:
                if key == 'permissions' and isinstance(request.data[key], dict):
                    group.setdefault('permissions', {}).update(request.data[key])
                else:
                    group[key] = request.data[key]

        profile.social['friend_groups'][group_uuid] = group
        _sync_social(profile)
        return Response({'uuid': group_uuid, **group})

    def delete(self, request, group_uuid):
        profile = _get_social(request.user)
        if group_uuid in profile.social.get('friend_groups', {}):
            del profile.social['friend_groups'][group_uuid]
            # Unassign friends from this group
            for fid, friend in profile.social.get('friends', {}).items():
                if friend.get('group') == group_uuid:
                    friend['group'] = ''
            _sync_social(profile)
        return Response(status=204)


class FollowersListView(APIView):
    """GET /social/followers/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_social(request.user)
        return Response({
            'followers': profile.social.get('followers', []),
            'count': len(profile.social.get('followers', [])),
        })


class FollowingListView(APIView):
    """GET /social/following/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_social(request.user)
        return Response({
            'following': profile.social.get('following', []),
            'count': len(profile.social.get('following', [])),
        })

class AllUsersView(APIView):
    """GET /social/all-users/"""
    permission_classes = []  # Public endpoint — показуємо список користувачів

    def get(self, request):
        from django.contrib.auth.models import User
        # Перебираємо УСІХ Django-юзерів і створюємо профілі якщо нема
        users = User.objects.all()
        result = []
        for u in users:
            # Пропускаємо сервісні акаунти (без email)
            if not u.email:
                continue
            profile, _ = UserProfile.objects.get_or_create(user=u)
            account = profile.account or {}
            # Каскадний фоллбек: account.display_name → first+last → email → username
            display_name = (
                account.get('display_name')
                or f"{u.first_name} {u.last_name}".strip()
                or (u.email.split('@')[0] if u.email else '')
                or u.username
            )
            result.append({
                'uuid': str(profile.uuid),
                'display_name': display_name,
                'avatar_url': account.get('avatar_url', ''),
                'tier': account.get('tier', 'Free')
            })
        return Response({'users': result})
