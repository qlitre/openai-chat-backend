from rest_framework import serializers
from .models import Conversation, Message


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    モデルシリアライザーのサブクラスで、
    必要に応じてフィールドを動的に含めるか除外することができます。
    """

    def __init__(self, *args, **kwargs):
        # インスタンス化時に 'fields' または 'exclude' キーを受け入れます
        fields = kwargs.pop('fields', None)
        exclude = kwargs.pop('exclude', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            # 'fields' が提供された場合、__all__以外のフィールドを削除します
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if exclude is not None:
            # 'exclude' が提供された場合、指定されたフィールドを削除します
            for field_name in exclude:
                self.fields.pop(field_name, None)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ('id', 'message', 'is_bot', 'created_at')


class ConversationSerializer(DynamicFieldsModelSerializer):
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
