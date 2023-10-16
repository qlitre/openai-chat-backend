from django.contrib import admin
from .models import Conversation, Message


class ConversationAdmin(admin.ModelAdmin):
    list_display = ('topic', 'user', 'created_at')


class MessageAdmin(admin.ModelAdmin):
    list_display = ('message', 'is_bot', 'user', 'tokens', 'created_at')


# Register your models here.
admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
