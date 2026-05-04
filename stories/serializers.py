from rest_framework import serializers
from .models import Story, StoryParticipant
from django.contrib.auth import get_user_model

User = get_user_model()

class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']

class StoryParticipantSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = StoryParticipant
        fields = ['id', 'user', 'role', 'joined_at']

class StoryListSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField()
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            'id', 'title', 'genre', 'owner',
            'max_authors', 'is_public', 'status',
            'created_at', 'participant_count'
        ]

    def get_participant_count(self, obj):
        return obj.participants.count()

class StoryDetailSerializer(serializers.ModelSerializer):
    owner = UserBasicSerializer(read_only=True)
    participants = StoryParticipantSerializer(
        source='storyparticipant_set',
        many=True,
        read_only=True
    )

    class Meta:
        model = Story
        fields = [
            'id', 'title', 'genre', 'owner',
            'max_authors', 'is_public', 'status',
            'created_at', 'participants'
        ]

class CreateStorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = ['title', 'genre', 'max_authors', 'is_public']

class StoryParticipantActionSerializer(serializers.Serializer):
    # Used for join/leave (no extra fields needed)
    pass