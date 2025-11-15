# services/llm_client.py
import google.generativeai as genai
from config import conf
from services.logger import bot_logger

class GeminiClient:
    """Асинхронный клиент для работы с Google Gemini API"""

    def __init__(self):
        """Инициализация клиента Gemini"""
        if not conf.llm.api_key:
            raise ValueError("GEMINI_API_KEY не найден в конфигурации")

        genai.configure(api_key=conf.llm.api_key)
        self.model = genai.GenerativeModel(conf.llm.model)
        bot_logger.log_info(f"GeminiClient инициализирован с моделью: {conf.llm.model}")

    async def rewrite_text(self, prompt: str, original_text: str) -> str:
        """
        Асинхронный рерайт текста с помощью Gemini API

        Args:
            prompt: Системный промпт из Google Sheets
            original_text: Оригинальный текст для рерайта

        Returns:
            str: Переписанный текст
        """
        try:
            # Формируем финальное сообщение для LLM
            full_prompt = f"{prompt}\n\nОригинальный текст: {original_text}\n\nПерепиши этот текст:"

            # Выполняем асинхронный вызов Gemini API
            response = await self.model.generate_content_async(full_prompt)

            # Извлекаем текст из ответа
            if response and response.text:
                rewritten_text = response.text.strip()
                # Удаляем служебные символы и лишние пробелы
                rewritten_text = rewritten_text.replace('\n\n', '\n').strip()

                bot_logger.log_info(f"Успешный рерайт текста через Gemini API")
                return rewritten_text
            else:
                bot_logger.log_error("Gemini API вернул пустой ответ")
                return original_text  # Возвращаем оригинал в случае ошибки

        except Exception as e:
            error_msg = f"Ошибка при вызове Gemini API: {str(e)}"
            bot_logger.log_error(error_msg)

            # Возвращаем оригинальный текст в случае ошибки
            return original_text
