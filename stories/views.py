from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q
import redis

from .models import Story, StoryParticipant
from .serializers import (
    StoryListSerializer, StoryDetailSerializer,
    CreateStorySerializer, StoryParticipantSerializer,
    StoryParticipantActionSerializer,
    StorySegmentSerializer
)
from .permissions import IsStoryParticipant, IsStoryOwner

class StoryViewSet(viewsets.ModelViewSet):
    queryset = Story.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return StoryListSerializer
        elif self.action == 'create':
            return CreateStorySerializer
        elif self.action in ['join', 'leave']:
            return StoryParticipantActionSerializer
        return StoryDetailSerializer

    def get_permissions(self):
        if self.action in ['join', 'leave', 'start']:
            # joining/leaving does not require being participant yet
            return [permissions.IsAuthenticated()]
        elif self.action in ['retrieve']:
            # Only participants can view story details + lobby
            return [permissions.IsAuthenticated(), IsStoryParticipant()]
        return super().get_permissions()

    def perform_create(self, serializer):
        story = serializer.save(owner=self.request.user)
        # Owner automatically joins as writer
        StoryParticipant.objects.create(
            user=self.request.user,
            story=story,
            role=StoryParticipant.Role.WRITER
        )

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        story = self.get_object()
        if story.status != Story.Status.LOBBY:
            return Response(
                {'error': 'Can only join while story is in lobby'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if story.participants.count() >= story.max_authors:
            return Response(
                {'error': 'Story is full'},
                status=status.HTTP_400_BAD_REQUEST
            )
        _, created = StoryParticipant.objects.get_or_create(
            user=request.user,
            story=story,
            defaults={'role': StoryParticipant.Role.WRITER}
        )
        if not created:
            return Response({'detail': 'Already a participant'})
        return Response({'detail': 'Joined successfully'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        story = self.get_object()
        participation = StoryParticipant.objects.filter(
            user=request.user,
            story=story
        )
        if not participation.exists():
            return Response({'detail': 'Not a participant'}, status=status.HTTP_400_BAD_REQUEST)
        participation.delete()
        return Response({'detail': 'Left the story'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        story = self.get_object()
        if story.owner != request.user:
            return Response(
                {'error': 'Only the owner can start the story'},
                status=status.HTTP_403_FORBIDDEN
            )
        if story.status != Story.Status.LOBBY:
            return Response(
                {'error': 'Story can only be started from lobby'},
                status=status.HTTP_400_BAD_REQUEST
            )
        story.status = Story.Status.ACTIVE
        story.save()
        
        # NEW: Initialize turn to story owner in Redis
        r = redis.from_url(settings.REDIS_URL)
        r.set(f'story:{story.id}:turn', story.owner.id)
        
        return Response({'detail': 'Story started', 'status': story.status})

    @action(detail=True, methods=['get'])
    def segments(self, request, pk=None):
        story = self.get_object()
        qs = story.segments.all().order_by('sequence_number')
        # You can add pagination here if needed
        serializer = StorySegmentSerializer(qs, many=True)
        return Response(serializer.data)
    # Only show stories where user is participant (my stories) and optionally public stories
    def get_queryset(self):
        user = self.request.user
        if self.action == 'list':
            # Return both public stories and the ones user participates in
            return Story.objects.filter(
                Q(participants=user) | Q(is_public=True)
            ).distinct()
        return Story.objects.all()   # detail/join will be filtered by permissions