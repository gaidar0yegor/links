# services/llm_client.py
import google.generativeai as genai
from config import conf
from services.logger import bot_logger

class GeminiClient:
    """Клиент для работы с Gemini API."""
    def __init__(self):
        # Получаем ключ из конфигурации
        api_key = conf.llm.api_key
        if not api_key:
            raise ValueError("LLM API ключ не найден в конфигурации.")

        # Настройка API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        bot_logger.log_info("GeminiClient", f"GeminiClient инициализирован с моделью: {self.model.model_name}:")

    async def rewrite_text(self, prompt: str, text: str) -> str | None:
        """Переписывает текст с помощью Gemini, используя заданный промпт."""
        try:
            # Формируем полный промпт
            full_prompt = f"{prompt}\n\n---\n\n{text}"
            
            # Асинхронный вызов API
            response = await self.model.generate_content_async(full_prompt)
            
            # Извлекаем текст из ответа
            if response.parts:
                return response.text.strip()
            return None
        except Exception as e:
            bot_logger.log_error("GeminiClient", e, f"Ошибка при вызове Gemini API: {e}:")
            return None
