from .models import Conversation, Message
from django.db.models import Q
from rest_framework import generics, status, pagination, response
from .serializers import ConversationSerializer, ConversationCreateSerializer, \
    MessageCreateSerializer
from .open_ai_client import OpenAIClient
from rest_framework.response import Response
from account.models import User
from rest_framework.permissions import IsAuthenticated, AllowAny
from collections import deque
import tiktoken
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
import json

# 開発中にgptに投げるかどうかを制御する変数
USE_GPT = True


def calc_token(s: str):
    """Token数を計算して返す"""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens_per_message = 8
    add_token = len(encoding.encode(s))
    return tokens_per_message + add_token


def build_history(conversation_id: int, prompt: str):
    """
    履歴を構築する
    とりあえず直近四回の会話履歴＋新しいprompt
    """
    queryset = Message.objects.filter(conversation__id=conversation_id)
    queryset = queryset.order_by('-created_at')[:4]

    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    # 実際は4097だが安全マージンをとって4000までとする
    # なんかcompletion用に1024確保しないといけないっぽい
    max_token = 4000 - 1024
    # ユーザーが送信したメッセージを加える
    ret = deque()
    ret.append({'role': 'user', 'content': prompt})
    num_tokens = calc_token(prompt)
    for query in queryset:
        role = 'user'
        if query.is_bot:
            role = 'assistant'
        # メッセージを足してもmax_token以内なら履歴に加える
        add_token = calc_token(query.message)
        if num_tokens + add_token <= max_token:
            num_tokens += add_token
            ret.appendleft({'role': role, 'content': query.message})
        else:
            break

    return num_tokens, list(ret)


class ChatGPTStreamView(APIView):
    """
    初回の会話作成時に呼び出されるストリームビュー
    """

    @staticmethod
    def generate_stream_response(stream_response):
        for chunk in stream_response:
            chat_completion_delta = chunk.choices[0].delta
            data = json.dumps(dict(chat_completion_delta))
            yield f'data: {data}\n\n'

    def post(self, request):
        prompt = self.request.data.get('prompt')
        messages = [{"role": "user", "content": prompt}]
        client = OpenAIClient()
        stream_response = client.generate_stream_response(messages)

        r = StreamingHttpResponse(self.generate_stream_response(stream_response), content_type='text/event-stream')
        r['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
        r['Cache-Control'] = 'no-cache'  # Ensure clients don't cache the data

        return r


class ChatGPTStreamWithHistoryView(APIView):
    """
    履歴付きのチャットストリームを提供
    """

    @staticmethod
    def generate_stream_response(stream_response):
        for chunk in stream_response:
            chat_completion_delta = chunk.choices[0].delta
            data = json.dumps(dict(chat_completion_delta))
            yield f'data: {data}\n\n'

    def post(self, request, *args, **kwargs):
        prompt = self.request.data.get('prompt')
        conversation_id = self.kwargs.get('pk')
        token, messages = build_history(conversation_id, prompt)

        # ここで一回promptの保存処理をする
        user_id = self.request.user.id
        conversation_instance = Conversation.objects.get(id=conversation_id)
        user_instance = User.objects.get(id=user_id)
        Message.objects.create(
            conversation=conversation_instance,
            user=user_instance,
            message=prompt,
            tokens=token,
            is_bot=False
        )

        client = OpenAIClient()
        stream_response = client.generate_stream_response(messages)

        r = StreamingHttpResponse(self.generate_stream_response(stream_response), content_type='text/event-stream')
        r['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
        r['Cache-Control'] = 'no-cache'  # Ensure clients don't cache the data

        return r


class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        return response.Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'totalPages': self.page.paginator.num_pages,
            'currentPage': self.page.number,
            'results': data,
            'pageSize': self.page_size,
        })


class ConversationList(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer(self, *args, **kwargs):
        """
        このビューで使用されるシリアライザーのインスタンスを返す
        """
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()

        fields = self.request.query_params.get('fields')
        if fields:
            fields = fields.split(',')
            kwargs['fields'] = fields

        exclude = self.request.query_params.get('exclude')
        if exclude:
            exclude = exclude.split(',')
            kwargs['exclude'] = exclude

        return serializer_class(*args, **kwargs)

    def get_queryset(self):
        user_id = self.request.user.id
        queryset = Conversation.objects.filter(user_id=user_id).prefetch_related('messages')
        # keyword検索
        keyword = self.request.query_params.get('q', None)
        """
        topicに含まれていたら検索ヒット
        もしくは
        topicに紐づくmessageに全てのキーワードが含まれていたら検索ヒット
        とする
        """
        if keyword:
            # トピックの検索
            for word in keyword.split(' '):
                queryset = queryset.filter(Q(topic__icontains=word))

            # メッセージの検索
            conversation_ids = set()
            first = True
            # ※一つにまとめることもできる。
            for word in keyword.split(' '):
                messages = Message.objects.filter(user_id=user_id)
                messages = messages.filter(Q(message__icontains=word))
                # 少なくとも今のキーワードにヒットした会話ID
                matched_conversation_ids = set(messages.values_list('conversation_id', flat=True))
                # 初回はそのままセット
                if first:
                    conversation_ids = matched_conversation_ids
                    first = False
                else:
                    # 2回目以降はintersectionで被ってるIDを抽出
                    conversation_ids = conversation_ids.intersection(matched_conversation_ids)
            conversations = Conversation.objects.filter(user_id=user_id)
            # topicで絞りこんだqueryとorでマージするイメージ
            queryset = queryset | conversations.filter(id__in=conversation_ids)

        return queryset.order_by('-created_at')


class ConversationDetail(generics.RetrieveAPIView):
    queryset = Conversation.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer


class ConversationCreate(generics.CreateAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        prompt = self.request.data.get('prompt')
        ai_res = self.request.data.get('ai_res')
        topic_token = 0
        client = OpenAIClient()
        topic_prompt = f'[prompt]\n{prompt}\n\n[ai]\n{ai_res}'
        topic_response = client.generate_topic_response(topic_prompt)
        topic = topic_response.choices[0].message.content.strip()
        topic_token += topic_response.usage.total_tokens
        user_id = self.request.user.id
        data = {'user': user_id,
                'topic': topic}
        serializer = ConversationCreateSerializer(data=data)
        if serializer.is_valid():
            conversation_instance = serializer.save()
            user_instance = User.objects.get(id=user_id)
            # Messageモデルにデータを保存
            # 初回はtopicのtokenを加える
            new_prompt = Message.objects.create(
                conversation=conversation_instance,
                user=user_instance,
                message=prompt,
                tokens=calc_token(prompt) + topic_token,
                is_bot=False
            )
            # AIの返事も追加
            new_ai_res = Message.objects.create(
                conversation=conversation_instance,
                user=user_instance,
                message=ai_res,
                tokens=calc_token(ai_res),
                is_bot=True
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MessageCreate(generics.CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        message = request.data['message']
        data = request.data.copy()
        user_id = request.user.id
        conversation_id = kwargs.get('conversation_id')
        token = calc_token(message)

        # 受け取ったデータにユーザーID、会話ID、トークンを追加
        data['user'] = user_id
        data['conversation'] = conversation_id
        data['token'] = token
        # シリアライザを使用してバリデーションと保存
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
