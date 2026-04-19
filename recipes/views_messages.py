"""
Phase 9: Messages Views
All messages stored in UserProfile.inbox JSONB.

Schema of UserProfile.inbox:
{
    "conversations": {
        "<conv_id>": {
            "type": "direct|group",
            "participants": ["<user_uuid>", ...],
            "group_name": "...",
            "group_icon": "...",
            "messages": [
                {
                    "id": "<msg_uuid>",
                    "author_uuid": "...",
                    "author_name": "...",
                    "text": "...",
                    "media_uuid": "...",
                    "created_at": "...",
                    "edited_at": null,
                    "deleted": false
                }
            ],
            "last_activity": "...",
            "created_at": "..."
        }
    },
    "unread_count": 0
}

Endpoints:
  GET    /messages/                              — list conversations (overview)
  GET    /messages/{conv_id}/                    — get conversation with messages
  POST   /messages/{user_uuid}/send/             — send message (creates DM or adds to existing)
  PATCH  /messages/{conv_id}/{msg_id}/           — edit message
  DELETE /messages/{conv_id}/{msg_id}/           — delete message (soft)
  POST   /messages/groups/                       — create group chat
  PATCH  /messages/groups/{group_id}/            — edit group (name, icon, participants)
  POST   /messages/groups/{group_id}/send/       — send message to group
"""
import uuid as uuid_mod
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile
from .sync_outbox import outbox_enqueue


def _get_inbox(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not isinstance(profile.inbox, dict):
        profile.inbox = {'conversations': {}, 'unread_count': 0}
        profile.save(update_fields=['inbox'])
    profile.inbox.setdefault('conversations', {})
    profile.inbox.setdefault('unread_count', 0)
    return profile


def _sync_inbox(profile):
    profile.save(update_fields=['inbox', 'updated_at'])
    outbox_enqueue(
        entity_type='user_profile',
        entity_uuid=profile.uuid,
        op='patch',
        payload={'uuid': str(profile.uuid), 'inbox': profile.inbox},
    )


def _find_dm_conv(profile, target_uuid):
    """Find existing DM conversation between profile and target."""
    my_uuid = str(profile.uuid)
    for conv_id, conv in profile.inbox.get('conversations', {}).items():
        if conv.get('type') != 'direct':
            continue
        participants = set(conv.get('participants', []))
        if participants == {my_uuid, target_uuid}:
            return conv_id
    return None


def _deliver_message(target_uuid, conv_id, conv_data, message):
    """Deliver message to another user's inbox."""
    try:
        target_profile = UserProfile.objects.get(uuid=target_uuid)
        inbox = target_profile.inbox or {'conversations': {}, 'unread_count': 0}
        inbox.setdefault('conversations', {})
        inbox.setdefault('unread_count', 0)

        if conv_id not in inbox['conversations']:
            inbox['conversations'][conv_id] = {
                **conv_data,
                'messages': [],
            }
        inbox['conversations'][conv_id]['messages'].append(message)
        inbox['conversations'][conv_id]['last_activity'] = message['created_at']
        inbox['unread_count'] = inbox.get('unread_count', 0) + 1

        target_profile.inbox = inbox
        target_profile.save(update_fields=['inbox', 'updated_at'])
    except UserProfile.DoesNotExist:
        pass


class ConversationListView(APIView):
    """GET /messages/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_inbox(request.user)
        convs = profile.inbox.get('conversations', {})
        # Return overview (no full messages, just last message preview)
        overview = {}
        for cid, conv in convs.items():
            msgs = conv.get('messages', [])
            last_msg = msgs[-1] if msgs else None
            overview[cid] = {
                'type': conv.get('type', 'direct'),
                'participants': conv.get('participants', []),
                'group_name': conv.get('group_name', ''),
                'message_count': len(msgs),
                'last_message': last_msg.get('text', '')[:100] if last_msg else '',
                'last_activity': conv.get('last_activity', ''),
            }
        return Response({
            'conversations': overview,
            'unread_count': profile.inbox.get('unread_count', 0),
        })


class ConversationDetailView(APIView):
    """GET /messages/{conv_id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id):
        profile = _get_inbox(request.user)
        conv = profile.inbox.get('conversations', {}).get(conv_id)
        if not conv:
            return Response({'error': 'Conversation not found'}, status=404)

        # Mark as read (reset unread for this conversation)
        if profile.inbox.get('unread_count', 0) > 0:
            profile.inbox['unread_count'] = max(0, profile.inbox['unread_count'] - 1)
            profile.save(update_fields=['inbox'])

        return Response({'conv_id': conv_id, **conv})


class SendDirectMessageView(APIView):
    """POST /messages/{user_uuid}/send/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_uuid):
        profile = _get_inbox(request.user)
        my_uuid = str(profile.uuid)

        if my_uuid == user_uuid:
            return Response({'error': 'Cannot message yourself'}, status=400)

        text = request.data.get('text', '').strip()
        media_uuid = request.data.get('media_uuid', '')
        if not text and not media_uuid:
            return Response({'error': 'Message text or media required'}, status=400)

        now = datetime.utcnow().isoformat()
        msg_id = str(uuid_mod.uuid4())

        message = {
            'id': msg_id,
            'author_uuid': my_uuid,
            'author_name': request.user.username,
            'text': text,
            'media_uuid': media_uuid,
            'created_at': now,
            'edited_at': None,
            'deleted': False,
        }

        # Find or create DM conversation
        conv_id = _find_dm_conv(profile, user_uuid)
        if not conv_id:
            conv_id = str(uuid_mod.uuid4())
            conv_data = {
                'type': 'direct',
                'participants': [my_uuid, user_uuid],
                'messages': [],
                'last_activity': now,
                'created_at': now,
            }
            profile.inbox['conversations'][conv_id] = conv_data
        else:
            conv_data = profile.inbox['conversations'][conv_id]

        profile.inbox['conversations'][conv_id]['messages'].append(message)
        profile.inbox['conversations'][conv_id]['last_activity'] = now
        _sync_inbox(profile)

        # Deliver to target
        _deliver_message(user_uuid, conv_id, {
            'type': 'direct',
            'participants': [my_uuid, user_uuid],
            'last_activity': now,
            'created_at': conv_data.get('created_at', now),
        }, message)

        return Response({'conv_id': conv_id, 'message': message}, status=201)


class EditMessageView(APIView):
    """PATCH/DELETE /messages/{conv_id}/{msg_id}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, conv_id, msg_id):
        profile = _get_inbox(request.user)
        conv = profile.inbox.get('conversations', {}).get(conv_id)
        if not conv:
            return Response({'error': 'Conversation not found'}, status=404)

        my_uuid = str(profile.uuid)
        for msg in conv.get('messages', []):
            if msg['id'] == msg_id and msg['author_uuid'] == my_uuid:
                if 'text' in request.data:
                    msg['text'] = request.data['text']
                msg['edited_at'] = datetime.utcnow().isoformat()
                _sync_inbox(profile)

                # Update in target's inbox too
                for p_uuid in conv.get('participants', []):
                    if p_uuid != my_uuid:
                        try:
                            tp = UserProfile.objects.get(uuid=p_uuid)
                            tc = (tp.inbox or {}).get('conversations', {}).get(conv_id)
                            if tc:
                                for tm in tc.get('messages', []):
                                    if tm['id'] == msg_id:
                                        tm['text'] = msg['text']
                                        tm['edited_at'] = msg['edited_at']
                                        tp.save(update_fields=['inbox', 'updated_at'])
                                        break
                        except UserProfile.DoesNotExist:
                            pass

                return Response(msg)

        return Response({'error': 'Message not found or not yours'}, status=404)

    def delete(self, request, conv_id, msg_id):
        profile = _get_inbox(request.user)
        conv = profile.inbox.get('conversations', {}).get(conv_id)
        if not conv:
            return Response({'error': 'Conversation not found'}, status=404)

        my_uuid = str(profile.uuid)
        for msg in conv.get('messages', []):
            if msg['id'] == msg_id and msg['author_uuid'] == my_uuid:
                msg['deleted'] = True
                msg['text'] = '[Повідомлення видалено]'
                _sync_inbox(profile)

                # Mark as deleted in target's inbox
                for p_uuid in conv.get('participants', []):
                    if p_uuid != my_uuid:
                        try:
                            tp = UserProfile.objects.get(uuid=p_uuid)
                            tc = (tp.inbox or {}).get('conversations', {}).get(conv_id)
                            if tc:
                                for tm in tc.get('messages', []):
                                    if tm['id'] == msg_id:
                                        tm['deleted'] = True
                                        tm['text'] = '[Повідомлення видалено]'
                                        tp.save(update_fields=['inbox', 'updated_at'])
                                        break
                        except UserProfile.DoesNotExist:
                            pass
                return Response(status=204)

        return Response({'error': 'Message not found or not yours'}, status=404)


class GroupChatCreateView(APIView):
    """POST /messages/groups/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_inbox(request.user)
        my_uuid = str(profile.uuid)

        participants = request.data.get('participants', [])
        if my_uuid not in participants:
            participants.insert(0, my_uuid)

        if len(participants) < 2:
            return Response({'error': 'Group needs at least 2 participants'}, status=400)

        now = datetime.utcnow().isoformat()
        group_id = str(uuid_mod.uuid4())
        conv_data = {
            'type': 'group',
            'participants': participants,
            'group_name': request.data.get('group_name', 'Group'),
            'group_icon': request.data.get('group_icon', 'users'),
            'messages': [],
            'last_activity': now,
            'created_at': now,
        }

        profile.inbox['conversations'][group_id] = conv_data
        _sync_inbox(profile)

        # Create in all participants' inboxes
        for p_uuid in participants:
            if p_uuid != my_uuid:
                try:
                    tp = UserProfile.objects.get(uuid=p_uuid)
                    tp_inbox = tp.inbox or {'conversations': {}, 'unread_count': 0}
                    tp_inbox.setdefault('conversations', {})
                    tp_inbox['conversations'][group_id] = {**conv_data, 'messages': []}
                    tp.inbox = tp_inbox
                    tp.save(update_fields=['inbox', 'updated_at'])
                except UserProfile.DoesNotExist:
                    pass

        return Response({'group_id': group_id, **conv_data}, status=201)


class GroupChatEditView(APIView):
    """PATCH /messages/groups/{group_id}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id):
        profile = _get_inbox(request.user)
        conv = profile.inbox.get('conversations', {}).get(group_id)
        if not conv or conv.get('type') != 'group':
            return Response({'error': 'Group not found'}, status=404)

        for key in ['group_name', 'group_icon']:
            if key in request.data:
                conv[key] = request.data[key]

        # Handle adding/removing participants
        if 'participants' in request.data:
            old_parts = set(conv['participants'])
            new_parts = set(request.data['participants'])
            my_uuid = str(profile.uuid)
            if my_uuid not in new_parts:
                new_parts.add(my_uuid)

            # Add new participants
            for p in new_parts - old_parts:
                try:
                    tp = UserProfile.objects.get(uuid=p)
                    tp_inbox = tp.inbox or {'conversations': {}, 'unread_count': 0}
                    tp_inbox.setdefault('conversations', {})
                    tp_inbox['conversations'][group_id] = {**conv, 'messages': []}
                    tp.inbox = tp_inbox
                    tp.save(update_fields=['inbox', 'updated_at'])
                except UserProfile.DoesNotExist:
                    pass

            # Remove old participants
            for p in old_parts - new_parts:
                try:
                    tp = UserProfile.objects.get(uuid=p)
                    tp_inbox = tp.inbox or {}
                    if group_id in tp_inbox.get('conversations', {}):
                        del tp_inbox['conversations'][group_id]
                        tp.inbox = tp_inbox
                        tp.save(update_fields=['inbox', 'updated_at'])
                except UserProfile.DoesNotExist:
                    pass

            conv['participants'] = list(new_parts)

        profile.inbox['conversations'][group_id] = conv
        _sync_inbox(profile)
        return Response({'group_id': group_id, **conv})


class GroupChatSendView(APIView):
    """POST /messages/groups/{group_id}/send/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        profile = _get_inbox(request.user)
        conv = profile.inbox.get('conversations', {}).get(group_id)
        if not conv or conv.get('type') != 'group':
            return Response({'error': 'Group not found'}, status=404)

        my_uuid = str(profile.uuid)
        text = request.data.get('text', '').strip()
        media_uuid = request.data.get('media_uuid', '')
        if not text and not media_uuid:
            return Response({'error': 'Message text or media required'}, status=400)

        now = datetime.utcnow().isoformat()
        msg_id = str(uuid_mod.uuid4())
        message = {
            'id': msg_id,
            'author_uuid': my_uuid,
            'author_name': request.user.username,
            'text': text,
            'media_uuid': media_uuid,
            'created_at': now,
            'edited_at': None,
            'deleted': False,
        }

        conv['messages'].append(message)
        conv['last_activity'] = now
        _sync_inbox(profile)

        # Deliver to all participants
        for p_uuid in conv.get('participants', []):
            if p_uuid != my_uuid:
                _deliver_message(p_uuid, group_id, {
                    'type': 'group',
                    'participants': conv['participants'],
                    'group_name': conv.get('group_name', 'Group'),
                    'group_icon': conv.get('group_icon', 'users'),
                    'last_activity': now,
                    'created_at': conv.get('created_at', now),
                }, message)

        return Response({'group_id': group_id, 'message': message}, status=201)
