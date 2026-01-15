from django.urls import path, include
from rest_framework.routers import DefaultRouter
# Categories API lives in the categories app now
from categories.api_views import CategoryViewSet

router = DefaultRouter()
router.register(r'', CategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
]
