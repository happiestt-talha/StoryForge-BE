from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StoryViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'stories', StoryViewSet, basename='story')

urlpatterns = [
    path('', include(router.urls)),
]