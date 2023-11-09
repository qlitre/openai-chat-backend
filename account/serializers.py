from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserCreatePasswordRetypeSerializer
from rest_framework import serializers


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        fields = ('id', 'email', 'first_name', 'last_name', 'password')

    def validate_first_name(self, value):
        # first_name フィールドのカスタムバリデーション
        if not value:
            raise serializers.ValidationError("名は必須です。")  # エラーメッセージは日本語で設定可能
        return value

    def validate_last_name(self, value):
        # last_name フィールドのカスタムバリデーション
        if not value:
            raise serializers.ValidationError("姓は必須です。")  # エラーメッセージは日本語で設定可能
        return value
