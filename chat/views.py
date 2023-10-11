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
USE_GPT = True
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


def get_ai_message_and_topic(prompt):
    ai_res = None
    topic = None
    if not USE_GPT:
        ai_res = """
                柴田聡子は、1986年12月11日に北海道札幌市で生まれた日本のミュージシャン、詩人です。
                彼女は武蔵野美術大学と東京藝術大学で学び、2010年から音楽活動を本格化させました。
                2012年にデビューアルバム『しばたさとこ島』をリリースし、2014年にはレコード会社P-VINEに移籍し、2ndアルバム『いじわる全集』をリリースしました。
                詩の才能も持ち合わせており、2016年に詩集『さばーく』を発表し、エルスール財団新人賞・現代詩部門を受賞しました。
                2017年には4thアルバム『愛の休日 DO YOU NEED A REST FROM LOVE?』をリリースし、オリコンアルバムチャートで71位にランクインしました。
                このアルバムには山本精一、岸田繁など多くの著名なアーティストが参加しています。
                """
        # topicもGPTにやらせる
        # この文章のトピックを20文字以内で書いて。他に余計な情報は載せずトピックだけ書いて返して。
        topic = "柴田聡子の音楽と詩の経歴"
    else:
        # 質問を投げる
        openai.api_key = os.getenv('API_KEY')
        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        ai_res = res.choices[0].message['content'].strip()
        # topicを生成
        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {'role': "system", "content": '以下の文章のトピックを20文字以内で返しなさい'},
                {"role": "user", "content": ai_res},
            ],
        )
        topic = res.choices[0].message['content'].strip()
    return ai_res, topic


class ConversationCreate(generics.CreateAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        message = self.request.query_params.get('prompt')

        # topicもGPTにやらせる
        # この文章のトピックを20文字以内で書いて。他に余計な情報は載せずトピックだけ書いて返して。
        ai_res, topic = get_ai_message_and_topic(prompt=message)
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
                message=message,
                is_bot=False
            )
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


def get_ai_message(prompt=''):
    if not USE_GPT:
        res = """
        カネコアヤノ（Kaneko Ayano）は、日本のシンガーソングライターです。彼女は以下のような特徴や経歴を持っています：
        デビュー: カネコアヤノは、2010年代初頭に音楽活動を開始し、その独自の歌詞やメロディーで注目を集めました。
        音楽スタイル: 彼女の楽曲は、日常の風景や感情を繊細に描写した歌詞と、シンプルながらも印象的なメロディーで知られています。アコースティックギターを中心としたアレンジが多いです。
        作品: カネコアヤノは、数多くのアルバムやシングルをリリースしています。その中でも、彼女の作品は多くのリスナーから愛されており、その音楽性や歌詞の世界観が高く評価されています。
        ライブ活動: 彼女は、日本国内を中心にライブ活動を展開しており、その熱量あるライブパフォーマンスも魅力の一つです。
        カネコアヤノは、その独特の声や歌詞の世界観、感受性豊かなメロディーで多くのファンに支持されています。彼女の楽曲は、多くの人々の心に寄り添い、共感を呼び起こすものとなっています。
        """

        return res

    openai.api_key = os.getenv('API_KEY')
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt},
        ],
    )
    print(res)
    return res.choices[0].message['content'].strip()


class AiMessageCreate(generics.CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        message_data = request.data.copy()
        prompt = request.data.get('message')
        res = get_ai_message(prompt)
        message_data['message'] = res

        serializer = MessageCreateSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
