import json
import redis
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .models import Story, StorySegment, StoryParticipant
from datetime import datetime

User = get_user_model()

redis_client = redis.from_url(settings.REDIS_URL)

class StoryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.story_id = self.scope['url_route']['kwargs']['story_id']
        self.room_group_name = f'story_{self.story_id}'

        # Authenticate
        token = self.scope['query_string'].decode().split('token=')[1] if 'token=' in self.scope.get('query_string', b'').decode() else None
        if not token:
            await self.close(code=4001)
            return

        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            self.user = await self.get_user(user_id)
        except (InvalidToken, TokenError, Exception):
            await self.close(code=4002)
            return

        # Check if user is participant of this story
        is_member = await self.is_participant(self.user, self.story_id)
        if not is_member:
            await self.close(code=4003)
            return

        self.user_id = self.user.id
        self.username = self.user.username

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send current turn state (if any)
        current_turn_user_id = redis_client.get(f'story:{self.story_id}:turn')
        if current_turn_user_id:
            try:
                turn_user = await self.get_user(int(current_turn_user_id.decode()))
                await self.send_json({
                    'type': 'turn_changed',
                    'user_id': turn_user.id,
                    'username': turn_user.username
                })
            except Exception:
                pass

        # Notify others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user.id,
                'username': self.username
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user.id,
                    'username': self.username
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Message handlers
    async def receive_json(self, content):
        msg_type = content.get('type')

        if msg_type == 'ping':
            await self.send_json({'type': 'pong'})

        elif msg_type == 'typing':
            await self.handle_typing(content)

        elif msg_type == 'submit_paragraph':
            await self.handle_submit_paragraph(content)

    async def handle_typing(self, content):
        is_typing = content.get('is_typing', False)
        # Only broadcast if the user is the current turn holder
        current_turn = redis_client.get(f'story:{self.story_id}:turn')
        if current_turn and int(current_turn) == self.user.id:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'user_id': self.user.id,
                    'username': self.username,
                    'is_typing': is_typing
                }
            )

    async def handle_submit_paragraph(self, content):
        paragraph = content.get('content', '').strip()
        if not paragraph:
            return

        # Check turn
        current_turn = redis_client.get(f'story:{self.story_id}:turn')
        if not current_turn or int(current_turn) != self.user.id:
            await self.send_json({'type': 'error', 'message': 'It is not your turn.'})
            return

        # Save segment to DB
        segment = await self.save_segment(self.story_id, self.user, paragraph)

        # Clear turn and assign next
        await self.assign_next_turn(self.story_id)

        # Broadcast new segment to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'new_segment',
                'segment': {
                    'id': segment.id,
                    'author_type': 'human',
                    'author_user': self.username,
                    'content': segment.content,
                    'sequence_number': segment.sequence_number,
                    'created_at': segment.created_at.isoformat()
                }
            }
        )

    async def assign_next_turn(self, story_id):
        # Round-robin among writers
        participants = await self.get_writer_participants(story_id)
        current_turn = redis_client.get(f'story:{story_id}:turn')
        current_index = 0
        if current_turn:
            try:
                user_ids = [p['user_id'] for p in participants]
                current_index = user_ids.index(int(current_turn))
                next_index = (current_index + 1) % len(user_ids)
            except (ValueError, IndexError):
                next_index = 0
        else:
            next_index = 0

        next_user_id = participants[next_index]['user_id']
        next_user = await self.get_user(next_user_id)

        # Set turn in Redis (no TTL for now)
        redis_client.set(f'story:{self.story_id}:turn', next_user_id)
        # Broadcast turn change
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'turn_changed',
                'user_id': next_user.id,
                'username': next_user.username
            }
        )

    async def save_segment(self, story_id, user, content):
        story = await self.get_story(story_id)
        # Get next sequence number
        last_seq = await self.get_last_sequence(story)
        new_seq = (last_seq + 1) if last_seq is not None else 1
        segment = await database_sync_to_async(StorySegment.objects.create)(
            story=story,
            author_type=StorySegment.AuthorType.HUMAN,
            author_user=user,
            content=content,
            sequence_number=new_seq
        )
        return segment

    # Group event handlers (broadcast out)
    async def new_segment(self, event):
        await self.send_json({
            'type': 'new_segment',
            'segment': event['segment']
        })

    async def turn_changed(self, event):
        await self.send_json({
            'type': 'turn_changed',
            'user_id': event['user_id'],
            'username': event['username']
        })

    async def user_typing(self, event):
        if event['user_id'] != self.user.id:
            await self.send_json({
                'type': 'user_typing',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            })

    async def user_joined(self, event):
        if event['user_id'] != self.user.id:
            await self.send_json({
                'type': 'user_joined',
                'user_id': event['user_id'],
                'username': event['username']
            })

    async def user_left(self, event):
        if event['user_id'] != self.user.id:
            await self.send_json({
                'type': 'user_left',
                'user_id': event['user_id'],
                'username': event['username']
            })

    # Database helper methods (sync, wrapped with database_sync_to_async)
    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)

    @database_sync_to_async
    def get_story(self, story_id):
        return Story.objects.get(id=story_id)

    @database_sync_to_async
    def is_participant(self, user, story_id):
        return StoryParticipant.objects.filter(user=user, story_id=story_id).exists()

    @database_sync_to_async
    def get_writer_participants(self, story_id):
        # Return list of dicts with user_id and role
        participants = StoryParticipant.objects.filter(
            story_id=story_id,
            role=StoryParticipant.Role.WRITER
        ).select_related('user').order_by('joined_at')
        return [{'user_id': p.user.id, 'role': p.role} for p in participants]

    @database_sync_to_async
    def get_last_sequence(self, story):
        last = StorySegment.objects.filter(story=story).order_by('-sequence_number').first()
        return last.sequence_number if last else None