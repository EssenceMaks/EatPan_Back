"""
Phase 10: Promo Code Views
Uses PromoCode and PromoCodeUsage models (already created in Phase 1).

Endpoints:
  GET    /promo-codes/                             — list all codes (admin only)
  POST   /promo-codes/                             — create code (admin only)
  GET    /promo-codes/{code}/                      — get code info
  PATCH  /promo-codes/{code}/                      — edit code
  DELETE /promo-codes/{code}/                      — deactivate code
  POST   /promo-codes/{code}/use/                  — use / redeem code
  POST   /promo-codes/{code}/gift/{user_uuid}/     — gift code to user
"""
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from .models import PromoCode, PromoCodeUsage, UserProfile
from .serializers import PromoCodeSerializer, PromoCodeUsageSerializer
from .sync_outbox import outbox_enqueue


class PromoCodeListView(APIView):
    """GET / POST /promo-codes/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Regular users can only see active codes; admins see all
        if request.user.is_staff:
            codes = PromoCode.objects.all()
        else:
            codes = PromoCode.objects.filter(is_active=True)

        serializer = PromoCodeSerializer(codes, many=True)
        return Response({'codes': serializer.data, 'count': len(serializer.data)})

    def post(self, request):
        # Only staff can create codes
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)

        serializer = PromoCodeSerializer(data=request.data)
        if serializer.is_valid():
            code = serializer.save(created_by=request.user)
            outbox_enqueue(
                entity_type='promo_code',
                entity_uuid=code.uuid,
                op='create',
                payload={'uuid': str(code.uuid), 'code': code.code},
            )
            return Response(PromoCodeSerializer(code).data, status=201)
        return Response(serializer.errors, status=400)


class PromoCodeDetailView(APIView):
    """GET / PATCH / DELETE /promo-codes/{code}/"""
    permission_classes = [AllowAny]

    def get(self, request, code):
        try:
            promo = PromoCode.objects.get(code=code)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code not found'}, status=404)

        serializer = PromoCodeSerializer(promo)
        data = serializer.data

        # If user is authenticated, check if they already used this code
        if request.user.is_authenticated:
            already_used = PromoCodeUsage.objects.filter(
                promo_code=promo,
                used_by=request.user,
            ).exists()
            data['already_used'] = already_used

        return Response(data)

    def patch(self, request, code):
        if not request.user.is_authenticated or not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)

        try:
            promo = PromoCode.objects.get(code=code)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code not found'}, status=404)

        # Update allowed fields
        if 'data' in request.data:
            promo.data = request.data['data']
        if 'is_active' in request.data:
            promo.is_active = request.data['is_active']
        if 'max_uses' in request.data:
            d = promo.data or {}
            d['max_uses'] = request.data['max_uses']
            promo.data = d

        promo.save()
        outbox_enqueue(
            entity_type='promo_code',
            entity_uuid=promo.uuid,
            op='update',
            payload={'uuid': str(promo.uuid), 'data': promo.data},
        )

        return Response(PromoCodeSerializer(promo).data)

    def delete(self, request, code):
        if not request.user.is_authenticated or not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)

        try:
            promo = PromoCode.objects.get(code=code)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code not found'}, status=404)

        promo.is_active = False
        promo.save(update_fields=['is_active'])
        outbox_enqueue(
            entity_type='promo_code',
            entity_uuid=promo.uuid,
            op='delete',
            payload={'uuid': str(promo.uuid)},
        )
        return Response(status=204)


class PromoCodeUseView(APIView):
    """POST /promo-codes/{code}/use/ — redeem a promo code"""
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        try:
            promo = PromoCode.objects.get(code=code, is_active=True)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code not found or inactive'}, status=404)

        # Check if already used by this user
        if PromoCodeUsage.objects.filter(promo_code=promo, used_by=request.user).exists():
            return Response({'error': 'Code already used'}, status=400)

        # Check max uses
        promo_data = promo.data or {}
        max_uses = promo_data.get('max_uses', 0)
        if max_uses > 0:
            current_uses = PromoCodeUsage.objects.filter(promo_code=promo).count()
            if current_uses >= max_uses:
                return Response({'error': 'Code usage limit reached'}, status=400)

        # Create usage record
        usage = PromoCodeUsage.objects.create(
            promo_code=promo,
            used_by=request.user,
        )

        # Apply promo reward to user profile
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        account = profile.account or {}
        promo_history = account.get('promo_history', [])
        promo_history.append({
            'code': code,
            'reward': promo_data.get('reward', {}),
            'used_at': datetime.utcnow().isoformat(),
        })
        account['promo_history'] = promo_history

        # Apply reward (e.g., upgrade tier, add credits)
        reward = promo_data.get('reward', {})
        if reward.get('tier'):
            account['tier'] = reward['tier']
        if reward.get('credits'):
            account['credits'] = account.get('credits', 0) + reward['credits']

        profile.account = account
        profile.save(update_fields=['account', 'updated_at'])

        outbox_enqueue(
            entity_type='promo_code_usage',
            entity_uuid=usage.uuid,
            op='create',
            payload={
                'uuid': str(usage.uuid),
                'code': code,
                'user_uuid': str(profile.uuid),
            },
        )

        return Response({
            'status': 'redeemed',
            'code': code,
            'reward': reward,
        })


class PromoCodeGiftView(APIView):
    """POST /promo-codes/{code}/gift/{user_uuid}/ — gift code to another user"""
    permission_classes = [IsAuthenticated]

    def post(self, request, code, user_uuid):
        try:
            promo = PromoCode.objects.get(code=code, is_active=True)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code not found or inactive'}, status=404)

        # Verify target user exists
        try:
            target_profile = UserProfile.objects.get(uuid=user_uuid)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Target user not found'}, status=404)

        # Check if target already used this code
        if PromoCodeUsage.objects.filter(promo_code=promo, used_by=target_profile.user).exists():
            return Response({'error': 'Target user already used this code'}, status=400)

        # Add to target's inbox as a gift notification
        inbox = target_profile.inbox or {'conversations': {}, 'unread_count': 0}
        inbox.setdefault('conversations', {})
        inbox['unread_count'] = inbox.get('unread_count', 0) + 1

        # Get sender profile
        sender_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        gift_data = {
            'type': 'promo_gift',
            'from_uuid': str(sender_profile.uuid),
            'from_name': request.user.username,
            'code': code,
            'reward': (promo.data or {}).get('reward', {}),
            'gifted_at': datetime.utcnow().isoformat(),
        }

        # Store as a special notification in user_data
        user_data = target_profile.user_data or {}
        notifications = user_data.get('notifications', [])
        notifications.append(gift_data)
        user_data['notifications'] = notifications
        target_profile.user_data = user_data
        target_profile.save(update_fields=['user_data', 'updated_at'])

        return Response({
            'status': 'gifted',
            'code': code,
            'to': user_uuid,
        })
