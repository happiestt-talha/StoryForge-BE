from django.conf import settings
from django.db import models

class Story(models.Model):
    class Status(models.TextChoices):
        LOBBY = 'lobby', 'Lobby'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    title = models.CharField(max_length=255)
    genre = models.CharField(max_length=50, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_stories'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='StoryParticipant',
        related_name='participated_stories'
    )
    max_authors = models.PositiveSmallIntegerField(default=5)
    is_public = models.BooleanField(default=False)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.LOBBY
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class StoryParticipant(models.Model):
    class Role(models.TextChoices):
        WRITER = 'writer', 'Writer'
        VOTER = 'voter', 'Voter'
        SPECTATOR = 'spectator', 'Spectator'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.WRITER
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'story')


class StorySegment(models.Model):
    class AuthorType(models.TextChoices):
        HUMAN = 'human', 'Human'
        AI = 'ai', 'AI'

    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE,
        related_name='segments'
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Used for forked stories'
    )
    author_type = models.CharField(
        max_length=5,
        choices=AuthorType.choices
    )
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    content = models.TextField()
    sequence_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence_number']


class AIBranch(models.Model):
    segment = models.ForeignKey(
        StorySegment,
        on_delete=models.CASCADE,
        related_name='branches'
    )
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Vote(models.Model):
    branch = models.ForeignKey(
        AIBranch,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    weight = models.IntegerField(default=1)

    class Meta:
        unique_together = ('branch', 'user')


class Illustration(models.Model):
    segment = models.ForeignKey(
        StorySegment,
        on_delete=models.CASCADE,
        related_name='illustrations'
    )
    prompt_used = models.TextField()
    image_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)