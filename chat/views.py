from django.shortcuts import render
from .models import Conversation, Message
from rest_framework import generics, pagination, response
from .serializers import ConversationSerializer, MessageSerializer, ConversationCreateSerializer, \
    MessageCreateSerializer


# Existing List views
class ConversationList(generics.ListAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer


class MessageList(generics.ListAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        return Message.objects.filter(conversation__id=conversation_id)


# New Create views
class ConversationCreate(generics.CreateAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationCreateSerializer


class MessageCreate(generics.CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageCreateSerializer
