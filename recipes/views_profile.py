"""
Phase 3: Profile & Account Views
Endpoints:
  GET    /profile/me/                   — get or create own profile
  PATCH  /profile/me/                   — partial update JSONB fields
  GET    /profile/{uuid}/public/        — public profile (filtered by permissions)
  PATCH  /account/tier/                 — update subscription tier
  POST   /account/referral/create/      — generate referral code
  POST   /account/referral/activate/    — activate someone's referral
"""
import uuid as uuid_mod
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import UserProfile
from .serializers import UserProfileSerializer, PublicProfileSerializer
from .sync_outbox import outbox_enqueue


class ProfileMeView(APIView):
    """GET / PATCH /profile/me/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # Allow partial updates to any JSONB field
        allowed_fields = [
            'tasks', 'account', 'meal_plan', 'pantry',
            'shopping', 'social', 'inbox', 'user_data'
        ]

        updated_fields = []
        for field in allowed_fields:
            if field in request.data:
                current = getattr(profile, field) or {}
                incoming = request.data[field]
                if isinstance(incoming, dict):
                    # Deep merge: update existing dict with incoming data
                    current.update(incoming)
                    setattr(profile, field, current)
                else:
                    setattr(profile, field, incoming)
                updated_fields.append(field)

        if updated_fields:
            profile.save(update_fields=updated_fields + ['updated_at'])
            outbox_enqueue(
                entity_type='user_profile',
                entity_uuid=profile.uuid,
                op='patch',
                payload={
                    'uuid': str(profile.uuid),
                    **{f: getattr(profile, f) for f in updated_fields}
                },
            )

        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)


class PublicProfileView(APIView):
    """GET /profile/{uuid}/public/"""
    permission_classes = [AllowAny]

    def get(self, request, uuid):
        try:
            profile = UserProfile.objects.get(uuid=uuid)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)

        # Filter based on friend_group permissions if viewer is authenticated
        serializer = PublicProfileSerializer(profile)
        data = serializer.data

        # If viewer is a friend, potentially reveal more info
        if request.user.is_authenticated:
            viewer_profile = UserProfile.objects.filter(user=request.user).first()
            if viewer_profile:
                friends = (profile.social or {}).get('friends', {})
                viewer_uuid = str(viewer_profile.uuid)
                if viewer_uuid in friends:
                    friend_data = friends[viewer_uuid]
                    group_id = friend_data.get('group')
                    groups = (profile.social or {}).get('friend_groups', {})
                    if group_id and group_id in groups:
                        perms = groups[group_id].get('permissions', {})
                        if perms.get('show_meal_plan'):
                            data['meal_plan'] = profile.meal_plan
                        if perms.get('show_pantry'):
                            data['pantry'] = profile.pantry

        return Response(data)


class AccountTierView(APIView):
    """PATCH /account/tier/ — update subscription tier"""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        account = profile.account or {}

        tier = request.data.get('tier')  # 'free', 'premium', 'pro'
        if tier not in ('free', 'premium', 'pro'):
            return Response({'error': 'Invalid tier. Must be: free, premium, pro'}, status=400)

        account['tier'] = tier
        account['tier_updated_at'] = str(uuid_mod.uuid1().time)  # timestamp
        profile.account = account
        profile.save(update_fields=['account', 'updated_at'])

        outbox_enqueue(
            entity_type='user_profile',
            entity_uuid=profile.uuid,
            op='patch',
            payload={'uuid': str(profile.uuid), 'account': profile.account},
        )

        return Response({'status': 'ok', 'tier': tier})


class ReferralCreateView(APIView):
    """POST /account/referral/create/ — generate a referral code"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        account = profile.account or {}

        if account.get('referral_code'):
            return Response({
                'referral_code': account['referral_code'],
                'message': 'Referral code already exists'
            })

        code = f"REF-{request.user.username[:8].upper()}-{uuid_mod.uuid4().hex[:6].upper()}"
        account['referral_code'] = code
        account['referral_uses'] = 0
        profile.account = account
        profile.save(update_fields=['account', 'updated_at'])

        outbox_enqueue(
            entity_type='user_profile',
            entity_uuid=profile.uuid,
            op='patch',
            payload={'uuid': str(profile.uuid), 'account': profile.account},
        )

        return Response({'referral_code': code}, status=201)


class ReferralActivateView(APIView):
    """POST /account/referral/activate/ — activate someone else's referral code"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip()
        if not code:
            return Response({'error': 'Referral code required'}, status=400)

        # Find the referrer by their referral code
        referrer_profile = None
        for p in UserProfile.objects.all():
            if (p.account or {}).get('referral_code') == code:
                referrer_profile = p
                break

        if not referrer_profile:
            return Response({'error': 'Invalid referral code'}, status=404)

        if referrer_profile.user == request.user:
            return Response({'error': 'Cannot use your own referral code'}, status=400)

        # Check if already activated
        my_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        my_account = my_profile.account or {}
        if my_account.get('referred_by'):
            return Response({'error': 'Already activated a referral'}, status=400)

        # Apply referral
        my_account['referred_by'] = str(referrer_profile.uuid)
        my_profile.account = my_account
        my_profile.save(update_fields=['account', 'updated_at'])

        # Increment referrer's uses
        ref_account = referrer_profile.account or {}
        ref_account['referral_uses'] = ref_account.get('referral_uses', 0) + 1
        referrer_profile.account = ref_account
        referrer_profile.save(update_fields=['account', 'updated_at'])

        return Response({'status': 'ok', 'referrer': str(referrer_profile.uuid)})
