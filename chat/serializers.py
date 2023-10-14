from rest_framework import serializers
from .models import Conversation, Message
from django.conf import settings


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ('id', 'message', 'is_bot', 'created_at')


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)  # messagesという名前で、Messageのリストを含める

    class Meta:
        model = Conversation
        fields = ('id', 'topic', 'created_at', 'messages')


class ConversationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = '__all__'


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'
