from django.contrib import admin
from .models import (
    Story, StoryParticipant, StorySegment,
    AIBranch, Vote, Illustration
)

admin.site.register(Story)
admin.site.register(StoryParticipant)
admin.site.register(StorySegment)
admin.site.register(AIBranch)
admin.site.register(Vote)
admin.site.register(Illustration)