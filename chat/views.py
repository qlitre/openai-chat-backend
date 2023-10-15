from .models import Conversation, Message
from django.db.models import Q
from rest_framework import generics, status, pagination, response
from .serializers import ConversationSerializer, MessageSerializer, ConversationCreateSerializer, \
    MessageCreateSerializer
from rest_framework.response import Response
from account.models import User
from rest_framework.permissions import IsAuthenticated
import openai
import os
from dotenv import load_dotenv

# 開発中にgptに投げるかどうかを制御する変数
USE_GPT = True
GPT_MODEL = 'gpt-3.5-turbo-0613'
MARKDOWN_SYSTEM_ORDER = 'マークダウン形式で返してください'
load_dotenv()


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
        keyword = self.request.query_params.get('keyword', None)
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


class MessageList(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        user_id = self.request.user.id
        return Message.objects.filter(conversation__id=conversation_id, user__id=user_id)


class ConversationCreate(generics.CreateAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        prompt = self.request.query_params.get('prompt')
        ai_res = None
        topic = None
        if not USE_GPT:
            from .ai_mock import get_mock_topic_and_response
            ai_res, topic = get_mock_topic_and_response()
        else:
            openai.api_key = os.getenv('API_KEY')
            res = openai.ChatCompletion.create(
                model=GPT_MODEL,
                messages=[
                    {'role': "system", "content": MARKDOWN_SYSTEM_ORDER},
                    {"role": "user", "content": prompt},
                ],
            )
            ai_res = res.choices[0].message['content']
            # topicを生成
            res = openai.ChatCompletion.create(
                model=GPT_MODEL,
                messages=[
                    {'role': "system", "content": '以下の文章のトピックを20文字以内で返しなさい'},
                    {"role": "user", "content": ai_res},
                ],
            )
            topic = res.choices[0].message['content'].strip()
        user_id = self.request.user.id
        data = {'user': user_id,
                'topic': topic}
        serializer = ConversationCreateSerializer(data=data)
        if serializer.is_valid():
            # Conversationのインスタンスを保存
            conversation_instance = serializer.save()
            user_instance = User.objects.get(id=user_id)
            # Messageモデルにデータを保存
            new_prompt = Message.objects.create(
                conversation=conversation_instance,
                user=user_instance,
                message=prompt,
                is_bot=False
            )
            # AIの返事も追加
            new_ai_res = Message.objects.create(
                conversation=conversation_instance,
                user=user_instance,
                message=ai_res,
                is_bot=True
            )
            prompt_serializer = MessageCreateSerializer(new_prompt)
            ai_res_serializer = MessageCreateSerializer(new_ai_res)
            response_data = {
                'conversation': serializer.data,
                'new_prompt': prompt_serializer.data,
                'new_ai_res': ai_res_serializer.data
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MessageCreate(generics.CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = MessageCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def build_prompt(conversation_id: int, prompt: str):
    """
    promptを構築する
    とりあえず直近四回の会話履歴＋新しいprompt
    """
    queryset = Message.objects.filter(conversation__id=conversation_id)
    queryset = queryset.order_by('-created_at')[:4]
    ret = [{'role': "system", "content": MARKDOWN_SYSTEM_ORDER}]
    for query in reversed(queryset):
        role = 'user'
        if query.is_bot:
            role = 'assistant'
        ret.append({'role': role, 'content': query.message})
    ret.append({'role': 'user', 'content': prompt})
    return ret


class AiMessageCreate(generics.CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        message_data = request.data.copy()
        prompt = request.data.get('message')
        msg = None
        conversation_id = kwargs.get('conversation_id')
        if not USE_GPT:
            from .ai_mock import get_mock_response
            msg = get_mock_response()
        else:
            openai.api_key = os.getenv('API_KEY')
            res = openai.ChatCompletion.create(
                model=GPT_MODEL,
                messages=build_prompt(conversation_id, prompt)
            )
            msg = res.choices[0].message['content'].strip()
        message_data['message'] = msg
        serializer = MessageCreateSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
