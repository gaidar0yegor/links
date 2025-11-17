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
        # Try different models - prioritize working ones
        model_names = ['gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
        self.model = None

        for model_name in model_names:
            try:
                self.model = genai.GenerativeModel(model_name)
                bot_logger.log_info("GeminiClient", f"Successfully initialized with model: {model_name}")
                break
            except Exception as e:
                bot_logger.log_error("GeminiClient", e, f"Failed to initialize model {model_name}, trying next...")
                continue

        if not self.model:
            # Fallback to config model if all else fails
            try:
                config_model = conf.llm.model
                self.model = genai.GenerativeModel(config_model)
                bot_logger.log_info("GeminiClient", f"Fallback to config model: {config_model}")
            except Exception as e:
                bot_logger.log_error("GeminiClient", e, "Could not initialize any Gemini model")
                raise ValueError("Could not initialize any Gemini model")

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
