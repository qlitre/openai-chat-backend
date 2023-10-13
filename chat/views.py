from .models import Conversation, Message
from rest_framework import generics, status, pagination, response
from .serializers import ConversationSerializer, MessageSerializer, ConversationCreateSerializer, \
    MessageCreateSerializer
from rest_framework.response import Response
from account.models import User
from rest_framework.permissions import AllowAny
import openai
import os
from dotenv import load_dotenv

# 開発中にgptに投げるかどうかを制御する変数
USE_GPT = False
gpt_model = 'gpt-3.5-turbo-0613'
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
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user_id = self.request.query_params.get('user_id')

        if not user_id:
            return Conversation.objects.none()  # 空のクエリセットを返します

        return Conversation.objects.filter(user_id=user_id).order_by('-created_at')


class MessageList(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        user_id = self.request.query_params.get('user_id')
        return Message.objects.filter(conversation__id=conversation_id, user__id=user_id)


class ConversationCreate(generics.CreateAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationCreateSerializer
    permission_classes = [AllowAny]

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
                model=gpt_model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            ai_res = res.choices[0].message['content'].strip()
            # topicを生成
            res = openai.ChatCompletion.create(
                model=gpt_model,
                messages=[
                    {'role': "system", "content": '以下の文章のトピックを20文字以内で返しなさい'},
                    {"role": "user", "content": ai_res},
                ],
            )
            topic = res.choices[0].message['content'].strip()
        user_id = self.request.query_params.get('user_id')
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
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = MessageCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def build_prompt(conversation_id: int, prompt: str):
    """
    promptを構築する
    とりあえず直近三回の会話履歴＋新しいprompt
    """
    queryset = Message.objects.filter(conversation__id=conversation_id)
    queryset = queryset.order_by('-created_at')[:3]
    ret = []
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
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        message_data = request.data.copy()
        prompt = request.data.get('message')
        msg = None
        if not USE_GPT:
            from .ai_mock import get_mock_response
            msg = get_mock_response()
        else:
            openai.api_key = os.getenv('API_KEY')
            conversation_id = kwargs.get('conversation_id')
            res = openai.ChatCompletion.create(
                model=gpt_model,
                messages=build_prompt(conversation_id, prompt)
            )
            msg = res.choices[0].message['content'].strip()

        message_data['message'] = msg
        serializer = MessageCreateSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
