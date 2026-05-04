from rest_framework.permissions import BasePermission

class IsStoryParticipant(BasePermission):
    """Allow access only to users who are participants of the story."""
    def has_object_permission(self, request, view, obj):
        return obj.participants.filter(id=request.user.id).exists()

class IsStoryOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user