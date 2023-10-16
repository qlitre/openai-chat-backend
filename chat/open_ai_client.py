import openai
import os
from dotenv import load_dotenv

load_dotenv()


class OpenAIClient:
    def __init__(self, model_name='gpt-3.5-turbo-0613'):
        self.model_name = model_name
        self.api_key = os.getenv('API_KEY')  # 環境変数からAPIキーを取得
        openai.api_key = self.api_key  # openaiライブラリにAPIキーをセット
        self.base_system_order = 'マークダウン形式で返してください'

    def generate_response_single_prompt(self, prompt: str, max_tokens: int = 1024):
        """
        チャットの単発のコンプリーションを生成する。
        """
        messages = [{'role': "system", "content": self.base_system_order},
                    {"role": "user", "content": prompt}]
        res = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens
        )
        return res

    def generate_topic_response(self, prompt: str, max_tokens: int = 64):
        """
        トピックをAIに提案してもらう
        """
        messages = [{'role': "system", "content": '以下の文章のトピックを20文字以内で返しなさい'},
                    {"role": "user", "content": prompt}]
        res = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens
        )
        return res

    def generate_response_with_history(self, messages: list, max_tokens: int = 1024):
        """
        履歴を与えてチャットのコンプリーションを生成する。
        """
        _messages = [{'role': "system", "content": self.base_system_order}]
        for elm in messages:
            _messages.append(elm)
        res = openai.ChatCompletion.create(
            model=self.model_name,
            messages=_messages,
            max_tokens=max_tokens
        )
        return res
