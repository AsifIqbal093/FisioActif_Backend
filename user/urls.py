from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateUserView,
    ManageUserView,
    CustomTokenObtainView,
    UserAdminViewSet,
    CustomerViewSet,
)
# Backwards compatibility: some modules expect ClientViewSet. Alias it to CustomerViewSet
ClientViewSet = CustomerViewSet
app_name = 'user'

# Create the router and register viewsets if needed
router = DefaultRouter()
router.register(r'users', UserAdminViewSet, basename='admin-users')
router.register(r'clients', ClientViewSet)


urlpatterns = [
    path('register/', CreateUserView.as_view(), name='register'),
    path('me/', ManageUserView.as_view(), name='user-profile'),
    path('login/', CustomTokenObtainView.as_view(), name='token_obtain'),
    path('', include(router.urls)),
]