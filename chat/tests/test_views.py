from unittest.mock import patch
from django.urls import reverse
from account.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from chat.models import Conversation, Message
from chat.serializers import ConversationSerializer, ConversationCreateSerializer, MessageCreateSerializer
from rest_framework.authtoken.models import Token
from pydantic import BaseModel
from typing import List


class MessageModel(BaseModel):
    content: str


class Choice(BaseModel):
    message: MessageModel


class Usage(BaseModel):
    total_tokens: int


class Response(BaseModel):
    usage: Usage
    choices: List[Choice]

    def total_tokens(self):
        return self.usage.total_tokens


class LoggedInTestCase(APITestCase):
    """各テストクラスで共通の事前準備処理をオーバーライド"""

    def setUp(self) -> None:
        """
        テストメソッド実行前の事前設定
        """
        password = 'password'
        self.user = User.objects.create_user(email='testuser@example.com', password=password)
        self.client = APIClient()
        self.client.login(email=self.user.email, password=password)
        # Tokenの生成
        self.token, created = Token.objects.get_or_create(user=self.user)

        # Tokenをリクエストヘッダーに設定
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)


class ConversationListTestCase(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.conversation1 = Conversation.objects.create(topic="Topic1", user=self.user)
        self.conversation2 = Conversation.objects.create(topic="Topic2", user=self.user)
        self.conversation3 = Conversation.objects.create(topic="Topic3", user=self.user)
        self.message1 = Message.objects.create(conversation=self.conversation1, message="Hello World", user=self.user)
        self.message2 = Message.objects.create(conversation=self.conversation2, message="Hello Django", user=self.user)
        self.message3 = Message.objects.create(conversation=self.conversation3, message="I Love Django", user=self.user)

    def test_get_conversations(self):
        """
        通常のGETリクエストをテスト
        """
        url = reverse('chat:conversation_list')  # URLパターンの名前を使用して逆引き
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversations = Conversation.objects.filter(user_id=self.user.id)
        serializer = ConversationSerializer(conversations, many=True)
        self.assertEqual(response.data['results'], serializer.data)

    def test_search_conversations_by_keyword(self):
        """キーワード検索のテスト"""
        url = reverse('chat:conversation_list')
        response = self.client.get(url, {'q': 'Hello Django'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], 2)
        response = self.client.get(url, {'q': 'Django'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        hit_expect = {2, 3}
        for m in response.data['results']:
            hit_expect.discard(m['id'])
        self.assertEqual(len(hit_expect), 0)

    def test_get_conversations_with_fields_and_exclude(self):
        """
        field、exclude指定のテスト
        """
        url = reverse('chat:conversation_list')
        response = self.client.get(url, {'fields': 'topic,id'}, format='json')
        self.assertEqual(response.status_code, 200)
        for conversation in response.data['results']:
            self.assertIn('topic', conversation)
            self.assertIn('id', conversation)
            self.assertNotIn('created_at', conversation)

        response = self.client.get(url, {'exclude': 'topic'}, format='json')
        self.assertEqual(response.status_code, 200)
        for conversation in response.data['results']:
            self.assertNotIn('topic', conversation)
            self.assertIn('id', conversation)


class ConversationDetailTestCase(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = Conversation.objects.create(topic="Sample Topic", user=self.user)

    def test_get_conversation_detail(self):
        """
        GETリクエストが成功することをテスト
        """
        url = reverse('chat:conversation_detail', kwargs={'pk': self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.conversation.id)
        self.assertEqual(response.data['topic'], self.conversation.topic)

    def test_get_conversation_detail_unauthenticated(self):
        """
        認証が切れている際に取得できないことをテスト
        """
        self.client.logout()

        url = reverse('chat:conversation_detail', kwargs={'pk': self.conversation.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ConversationCreateTestCase(LoggedInTestCase):
    def setUp(self):
        super(ConversationCreateTestCase, self).setUp()

    @patch('chat.views.OpenAIClient')
    def test_create_conversation(self, mock_openai):
        """
        会話の作成をテスト
        """
        # OpenAIのレスポンスをモック化
        mock_openai.return_value.generate_response_single_prompt.return_value = Response(**{
            'usage': {'total_tokens': 10},
            'choices': [{'message': {'content': 'Mocked AI response'}}]
        })
        mock_openai.return_value.generate_topic_response.return_value = Response(**{
            'usage': {'total_tokens': 10},
            'choices': [{'message': {'content': 'Mocked Topic'}}]
        })

        url = reverse('chat:conversation_create')
        data = {'prompt': 'Test prompt'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Conversation.objects.filter(user=self.user, topic='Mocked Topic').exists())
        self.assertTrue(
            Message.objects.filter(conversation__user=self.user, message='Test prompt', is_bot=False).exists())
        self.assertTrue(
            Message.objects.filter(conversation__user=self.user, message='Mocked AI response', is_bot=True).exists())

        conversation_serializer = ConversationCreateSerializer(
            Conversation.objects.get(user=self.user, topic='Mocked Topic'))
        prompt_serializer = MessageCreateSerializer(
            Message.objects.get(conversation__user=self.user, message='Test prompt'))
        ai_res_serializer = MessageCreateSerializer(
            Message.objects.get(conversation__user=self.user, message='Mocked AI response'))

        expected_data = {
            'conversation': conversation_serializer.data,
            'new_prompt': prompt_serializer.data,
            'new_ai_res': ai_res_serializer.data
        }
        self.assertEqual(response.data, expected_data)

    def test_create_conversation_unauthenticated(self):
        """
        ログアウト時に作成できないことをテスト
        """
        self.client.logout()
        url = reverse('chat:conversation_create')
        data = {'prompt': 'Test prompt'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MessageCreateTestCase(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = Conversation.objects.create(topic="Test Topic", user=self.user)
        self.valid_payload = {
            'message': 'Hello ChatGPT',
            'user': self.user.id,
            'is_bot': False,
            'conversation': self.conversation.id
        }
        self.invalid_payload = {
            'conversation': '',
            'message': '',
            'user': '',
            'is_bot': ''
        }

    @patch('chat.views.OpenAIClient')
    def test_create_message_with_valid_data(self, mock_openai):
        mock_openai.return_value.generate_response_with_history.return_value = Response(**{
            'usage': {'total_tokens': 10},
            'choices': [{'message': {'content': 'Mocked AI response'}}]
        })
        data = {'message': 'Hello, AI!', 'is_bot': True}

        response = self.client.post(
            reverse('chat:message_create', kwargs={'conversation_id': self.conversation.id}),
            data,
            format='json'
        )
        expected_response = 'Mocked AI response'
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Message.objects.filter(message='Hello, AI!').exists())
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(response.data['message'], expected_response)
        self.assertTrue(Message.objects.filter(message=expected_response).exists())

    def test_create_message_with_invalid_data(self):
        # 例: messageキーが欠落しているペイロード
        response = self.client.post(
            reverse('chat:message_create', kwargs={'conversation_id': self.conversation.id}),
            self.invalid_payload
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_message_unauthenticated(self):
        """
        ログアウト時に作成できないことをテスト
        """
        self.client.logout()
        url = reverse('chat:message_create', kwargs={'conversation_id': self.conversation.id})
        response = self.client.post(url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
