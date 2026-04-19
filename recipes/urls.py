from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RecipeViewSet, RecipeBookViewSet, RecipeCategoryViewSet, UserRecipeStateViewSet, RecipeCommentViewSet, RecipeReactionViewSet, CommentReactionViewSet, MediaUploadView, MediaResolveView

# Phase 3: Profile & Account
from .views_profile import (
    ProfileMeView, PublicProfileView,
    AccountTierView, ReferralCreateView, ReferralActivateView,
)

# Phase 4: Tasks
from .views_tasks import (
    TaskListView, TaskDetailView, TaskCommentView,
    TaskGroupListView, TaskGroupDetailView, TaskGroupShareView,
)

# Phase 5: Meal Plan
from .views_meal_plan import (
    MealPlanListView, MealPlanDetailView,
    MealPlanBindRecipeView, MealPlanUnbindRecipeView,
    MealPlanLabelListView, MealPlanLabelDetailView,
)

# Phase 6: Pantry
from .views_pantry import (
    PantryListView, PantryItemView,
    PantryLocationView, PantryExpirationReportView,
)

# Phase 7: Shopping
from .views_shopping import (
    ShoppingOverviewView, ShoppingListView,
    ShoppingListShareView, ShoppingItemView,
)

# Phase 8: Social
from .views_social import (
    FollowView, FriendView,
    FriendGroupListView, FriendGroupDetailView,
    FollowersListView, FollowingListView,
    AllUsersView,
)

# Phase 9: Messages
from .views_messages import (
    ConversationListView, ConversationDetailView,
    SendDirectMessageView, EditMessageView,
    GroupChatCreateView, GroupChatEditView, GroupChatSendView,
)

# Phase 10: Promo Codes
from .views_promo import (
    PromoCodeListView, PromoCodeDetailView,
    PromoCodeUseView, PromoCodeGiftView,
)


# ============================================================
# DRF Router for existing ViewSets
# ============================================================
router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')
router.register(r'recipe-books', RecipeBookViewSet, basename='recipebook')
router.register(r'categories', RecipeCategoryViewSet, basename='category')
router.register(r'user-recipe-states', UserRecipeStateViewSet, basename='userrecipestate')
router.register(r'comments', RecipeCommentViewSet, basename='comment')
router.register(r'reactions/recipe', RecipeReactionViewSet, basename='recipereaction')
router.register(r'reactions/comment', CommentReactionViewSet, basename='commentreaction')


urlpatterns = [
    # ============================================================
    # Media (existing)
    # ============================================================
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
    path('media/<uuid:uuid>/', MediaResolveView.as_view(), name='media-resolve'),

    # ============================================================
    # Phase 3: Profile & Account
    # ============================================================
    path('profile/me/', ProfileMeView.as_view(), name='profile-me'),
    path('profile/<uuid:uuid>/public/', PublicProfileView.as_view(), name='profile-public'),
    path('account/tier/', AccountTierView.as_view(), name='account-tier'),
    path('account/referral/create/', ReferralCreateView.as_view(), name='referral-create'),
    path('account/referral/activate/', ReferralActivateView.as_view(), name='referral-activate'),

    # ============================================================
    # Phase 4: Tasks
    # ============================================================
    path('tasks/', TaskListView.as_view(), name='task-list'),
    path('tasks/<str:task_uuid>/', TaskDetailView.as_view(), name='task-detail'),
    path('tasks/<str:task_uuid>/comments/', TaskCommentView.as_view(), name='task-comment-create'),
    path('tasks/<str:task_uuid>/comments/<str:cid>/', TaskCommentView.as_view(), name='task-comment-detail'),
    path('task-groups/', TaskGroupListView.as_view(), name='taskgroup-list'),
    path('task-groups/<str:group_uuid>/', TaskGroupDetailView.as_view(), name='taskgroup-detail'),
    path('task-groups/<str:group_uuid>/share/', TaskGroupShareView.as_view(), name='taskgroup-share'),

    # ============================================================
    # Phase 5: Meal Plan
    # ============================================================
    path('meal-plan/', MealPlanListView.as_view(), name='mealplan-list'),
    path('meal-plan/labels/', MealPlanLabelListView.as_view(), name='mealplan-label-list'),
    path('meal-plan/labels/<str:label_uuid>/', MealPlanLabelDetailView.as_view(), name='mealplan-label-detail'),
    path('meal-plan/<str:entry_uuid>/', MealPlanDetailView.as_view(), name='mealplan-detail'),
    path('meal-plan/<str:entry_uuid>/bind-recipe/', MealPlanBindRecipeView.as_view(), name='mealplan-bind'),
    path('meal-plan/<str:entry_uuid>/unbind-recipe/<str:recipe_uuid>/', MealPlanUnbindRecipeView.as_view(), name='mealplan-unbind'),

    # ============================================================
    # Phase 6: Pantry
    # ============================================================
    path('pantry/', PantryListView.as_view(), name='pantry-list'),
    path('pantry/items/', PantryItemView.as_view(), name='pantry-item-create'),
    path('pantry/items/<str:item_uuid>/', PantryItemView.as_view(), name='pantry-item-detail'),
    path('pantry/locations/', PantryLocationView.as_view(), name='pantry-location-list'),
    path('pantry/locations/<str:loc_uuid>/', PantryLocationView.as_view(), name='pantry-location-detail'),
    path('pantry/expiration-report/', PantryExpirationReportView.as_view(), name='pantry-expiration'),

    # ============================================================
    # Phase 7: Shopping
    # ============================================================
    path('shopping/', ShoppingOverviewView.as_view(), name='shopping-overview'),
    path('shopping/lists/', ShoppingListView.as_view(), name='shopping-list-create'),
    path('shopping/lists/<str:list_uuid>/', ShoppingListView.as_view(), name='shopping-list-detail'),
    path('shopping/lists/<str:list_uuid>/share/', ShoppingListShareView.as_view(), name='shopping-list-share'),
    path('shopping/lists/<str:list_uuid>/items/', ShoppingItemView.as_view(), name='shopping-item-create'),
    path('shopping/lists/<str:list_uuid>/items/<str:item_uuid>/', ShoppingItemView.as_view(), name='shopping-item-detail'),

    # ============================================================
    # Phase 8: Social
    # ============================================================
    path('social/follow/<str:target_uuid>/', FollowView.as_view(), name='social-follow'),
    path('social/friends/<str:target_uuid>/', FriendView.as_view(), name='social-friend'),
    path('social/friend-groups/', FriendGroupListView.as_view(), name='social-friendgroup-list'),
    path('social/friend-groups/<str:group_uuid>/', FriendGroupDetailView.as_view(), name='social-friendgroup-detail'),
    path('social/followers/', FollowersListView.as_view(), name='social-followers'),
    path('social/following/', FollowingListView.as_view(), name='social-following'),
    path('social/all-users/', AllUsersView.as_view(), name='social-all-users'),

    # ============================================================
    # Phase 9: Messages
    # ============================================================
    path('messages/', ConversationListView.as_view(), name='messages-list'),
    path('messages/groups/', GroupChatCreateView.as_view(), name='messages-group-create'),
    path('messages/groups/<str:group_id>/', GroupChatEditView.as_view(), name='messages-group-edit'),
    path('messages/groups/<str:group_id>/send/', GroupChatSendView.as_view(), name='messages-group-send'),
    path('messages/<str:conv_id>/', ConversationDetailView.as_view(), name='messages-detail'),
    path('messages/<str:user_uuid>/send/', SendDirectMessageView.as_view(), name='messages-dm-send'),
    path('messages/<str:conv_id>/<str:msg_id>/', EditMessageView.as_view(), name='messages-edit'),

    # ============================================================
    # Phase 10: Promo Codes
    # ============================================================
    path('promo-codes/', PromoCodeListView.as_view(), name='promo-list'),
    path('promo-codes/<str:code>/', PromoCodeDetailView.as_view(), name='promo-detail'),
    path('promo-codes/<str:code>/use/', PromoCodeUseView.as_view(), name='promo-use'),
    path('promo-codes/<str:code>/gift/<str:user_uuid>/', PromoCodeGiftView.as_view(), name='promo-gift'),

    # ============================================================
    # DRF Router (existing ViewSets)
    # ============================================================
    path('', include(router.urls)),
]
