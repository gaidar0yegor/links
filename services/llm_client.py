# services/llm_client.py
import requests
from config import conf
from services.logger import bot_logger

class OpenAIClient:
    """Клиент для работы с OpenAI API using direct requests."""
    def __init__(self):
        # Получаем ключ из конфигурации
        api_key = conf.llm.api_key
        if not api_key:
            raise ValueError("LLM API ключ не найден в конфигурации.")

        # Use direct requests approach to avoid httpx proxy issues
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.model = conf.llm.model
        self.session = requests.Session()
        # Configure session to not use proxies
        self.session.proxies = {}
        self.session.trust_env = False  # Don't use environment proxy settings

        bot_logger.log_info("OpenAIClient", f"OpenAI client initialized with direct requests for model: {self.model}")

    async def rewrite_text(self, prompt: str, text: str) -> str | None:
        """Переписывает текст с помощью OpenAI, используя прямые HTTP запросы."""
        try:
            # Формируем полный промпт
            full_prompt = f"{prompt}\n\n---\n\n{text}"
            print(f"DEBUG: LLM Client - Making API call with prompt length: {len(full_prompt)}")

            # Prepare the request payload
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that rewrites text for social media posts."},
                    {"role": "user", "content": full_prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }

            # Make the API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            print(f"DEBUG: LLM Client - Sending request to {self.base_url}/chat/completions")
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=30
            )

            print(f"DEBUG: LLM Client - Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()

            # Extract the response text
            if result.get("choices") and len(result["choices"]) > 0:
                response_text = result["choices"][0]["message"]["content"].strip()
                print(f"DEBUG: LLM Client - Got response, length: {len(response_text)}")
                return response_text
            print(f"DEBUG: LLM Client - No choices in response")
            return None

        except Exception as e:
            print(f"DEBUG: LLM Client - Exception: {e}")
            bot_logger.log_error("OpenAIClient", e, f"Ошибка при вызове OpenAI API: {e}")
            return None
