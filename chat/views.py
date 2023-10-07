from .models import Conversation, Message
from rest_framework import generics, status
from .serializers import ConversationSerializer, MessageSerializer, ConversationCreateSerializer, \
    MessageCreateSerializer
from rest_framework.response import Response


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

    def create(self, request, *args, **kwargs):
        # リクエストから必要なデータを取得
        conversation_id = self.kwargs.get('conversation_id')  # URLからconversation_idを取得
        # リクエストデータからメッセージを取得
        message_data = request.data.copy()
        message_data['conversation'] = conversation_id
        # todo:認証周りを作成後に実装
        # user = self.request.user  # リクエストを送信したユーザー
        message_data['user'] = 1
        # シリアライザーを使用してメッセージを作成・保存
        serializer = MessageCreateSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetAiRes(generics.CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageCreateSerializer

    def create(self, request, *args, **kwargs):
        # リクエストから必要なデータを取得
        conversation_id = self.kwargs.get('conversation_id')  # URLからconversation_idを取得
        # リクエストデータからメッセージを取得
        message_data = request.data.copy()
        message_data['conversation'] = conversation_id
        # todo:認証周りを作成後に実装
        # user = self.request.user  # リクエストを送信したユーザー
        message_data['user'] = 1
        # todo:実際はこのタイミングでChatGPTにリクエストをする
        import time
        time.sleep(1)
        res = """
        カネコアヤノ（Kaneko Ayano）は、日本のシンガーソングライターです。彼女は以下のような特徴や経歴を持っています：
        デビュー: カネコアヤノは、2010年代初頭に音楽活動を開始し、その独自の歌詞やメロディーで注目を集めました。
        音楽スタイル: 彼女の楽曲は、日常の風景や感情を繊細に描写した歌詞と、シンプルながらも印象的なメロディーで知られています。アコースティックギターを中心としたアレンジが多いです。
        作品: カネコアヤノは、数多くのアルバムやシングルをリリースしています。その中でも、彼女の作品は多くのリスナーから愛されており、その音楽性や歌詞の世界観が高く評価されています。
        ライブ活動: 彼女は、日本国内を中心にライブ活動を展開しており、その熱量あるライブパフォーマンスも魅力の一つです。
        カネコアヤノは、その独特の声や歌詞の世界観、感受性豊かなメロディーで多くのファンに支持されています。彼女の楽曲は、多くの人々の心に寄り添い、共感を呼び起こすものとなっています。
        """
        message_data['message'] = res

        # シリアライザーを使用してメッセージを作成・保存
        serializer = MessageCreateSerializer(data=message_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
