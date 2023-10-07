from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('conversations/', views.ConversationList.as_view(), name='conversation_list'),
    path('conversations/create/', views.ConversationCreate.as_view(), name='conversation_create'),
    path('conversations/<int:conversation_id>/messages/', views.MessageList.as_view(), name='message_list'),
    path('conversations/<int:conversation_id>/messages/create/', views.MessageCreate.as_view(), name='message_create'),
    path('conversations/<int:conversation_id>/messages/get_ai_res/', views.GetAiRes.as_view(), name='get_ai_res'),
]
