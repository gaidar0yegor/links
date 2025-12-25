# services/llm_client.py
import requests
import asyncio
from config import conf
from services.logger import bot_logger

# Глобальный семафор для ограничения параллельных запросов к OpenAI API
# Максимум 2 параллельных запроса одновременно
_openai_semaphore = asyncio.Semaphore(2)

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

    async def rewrite_text(self, prompt: str, text: str, language: str = 'en', char_limit: int = 1024) -> str | None:
        """Переписывает текст с помощью OpenAI, используя прямые HTTP запросы с retry логикой."""
        # Используем семафор для ограничения параллельных запросов к OpenAI API
        async with _openai_semaphore:
            max_retries = 3
            base_delay = 2.0  # Начальная задержка 2 секунды
            
            # Формируем полный промпт
            full_prompt = f"{prompt}\n\n---\n\n{text}"

            language_map = {
                'en': 'English',
                'it': 'Italian',
                'es': 'Spanish',
                'ru': 'Russian',
                'de': 'German'
            }
            language_name = language_map.get(language, 'English')

            system_prompt = (
                "You are a helpful assistant that rewrites text for social media posts. "
                f"The response must be in {language_name}. "
                f"The total length of your response must not exceed {char_limit} characters."
            )

            # Prepare the request payload
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                "max_tokens": 350,
                "temperature": 0.7
            }

            # Make the API request with retry logic
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            for attempt in range(max_retries):
                try:
                    print(f"DEBUG: LLM Client - Sending request to {self.base_url}/chat/completions (attempt {attempt + 1}/{max_retries})")
                    response = self.session.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=30
                    )

                    print(f"DEBUG: LLM Client - Response status: {response.status_code}")
                    
                    # Обработка 429 ошибки (Rate Limit) с retry
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            # Экспоненциальная задержка: 2s, 4s, 8s
                            wait_time = base_delay * (2 ** attempt)
                            
                            # Пытаемся получить Retry-After из заголовков (если есть)
                            retry_after = response.headers.get('Retry-After')
                            if retry_after:
                                try:
                                    retry_after_seconds = float(retry_after)
                                    # Используем Retry-After только если он разумный (не больше 60 секунд)
                                    # Иначе используем экспоненциальную задержку для быстрых попыток
                                    if retry_after_seconds <= 60:
                                        wait_time = retry_after_seconds
                                        print(f"⚠️ Rate limit (429) - using Retry-After header: {wait_time}s")
                                    else:
                                        print(f"⚠️ Rate limit (429) - Retry-After слишком большой ({retry_after_seconds:.0f}s), используем экспоненциальную задержку: {wait_time}s")
                                except ValueError:
                                    pass
                            
                            print(f"⚠️ Rate limit (429) - retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"❌ Rate limit (429) - max retries ({max_retries}) exceeded")
                            bot_logger.log_error("OpenAIClient", Exception("Rate limit exceeded"), "OpenAI API rate limit exceeded after retries")
                            return None
                    
                    # Для других HTTP ошибок тоже делаем retry
                    if response.status_code >= 500:
                        if attempt < max_retries - 1:
                            wait_time = base_delay * (2 ** attempt)
                            print(f"⚠️ Server error ({response.status_code}) - retrying in {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                    
                    # Проверяем на другие ошибки
                    response.raise_for_status()
                    result = response.json()

                    # Extract the response text
                    if result.get("choices") and len(result["choices"]) > 0:
                        response_text = result["choices"][0]["message"]["content"].strip()
                        print(f"DEBUG: LLM Client - Got response, length: {len(response_text)}")
                        return response_text
                    print(f"DEBUG: LLM Client - No choices in response")
                    return None

                except requests.exceptions.HTTPError as e:
                    # Обработка HTTP ошибок (кроме 429, которая уже обработана выше)
                    if e.response and e.response.status_code == 429:
                        # Должно быть обработано выше, но на всякий случай
                        if attempt < max_retries - 1:
                            wait_time = base_delay * (2 ** attempt)
                            retry_after = e.response.headers.get('Retry-After')
                            if retry_after:
                                try:
                                    retry_after_seconds = float(retry_after)
                                    # Используем Retry-After только если он разумный (не больше 60 секунд)
                                    if retry_after_seconds <= 60:
                                        wait_time = retry_after_seconds
                                    else:
                                        print(f"⚠️ HTTP 429 Error - Retry-After слишком большой ({retry_after_seconds:.0f}s), используем экспоненциальную задержку: {wait_time}s")
                                except ValueError:
                                    pass
                            print(f"⚠️ HTTP 429 Error - retrying in {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                    
                    # Для других HTTP ошибок (4xx кроме 429) не делаем retry
                    if e.response and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                        print(f"DEBUG: LLM Client - Client error ({e.response.status_code}): {e}")
                        bot_logger.log_error("OpenAIClient", e, f"Ошибка клиента при вызове OpenAI API: {e}")
                        return None
                    
                    # Для 5xx ошибок делаем retry
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        print(f"⚠️ HTTP Error ({e.response.status_code if e.response else 'unknown'}) - retrying in {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"DEBUG: LLM Client - HTTP Exception after retries: {e}")
                        bot_logger.log_error("OpenAIClient", e, f"Ошибка при вызове OpenAI API после retries: {e}")
                        return None
                        
                except requests.exceptions.RequestException as e:
                    # Обработка сетевых ошибок (timeout, connection error и т.д.)
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        print(f"⚠️ Network error ({type(e).__name__}) - retrying in {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"DEBUG: LLM Client - Network Exception after retries: {e}")
                        bot_logger.log_error("OpenAIClient", e, f"Сетевая ошибка при вызове OpenAI API после retries: {e}")
                        return None
                        
                except Exception as e:
                    # Обработка всех остальных ошибок
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        print(f"⚠️ Unexpected error ({type(e).__name__}) - retrying in {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"DEBUG: LLM Client - Exception after retries: {e}")
                        bot_logger.log_error("OpenAIClient", e, f"Ошибка при вызове OpenAI API после retries: {e}")
                        return None
