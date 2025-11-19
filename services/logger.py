# services/logger.py
import logging
import sys
from datetime import datetime

# Настройка базового логирования (в консоль и, опционально, в файл)
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Дополнительный класс для бизнес-логирования (если нужно писать в PostgreSQL)
class BotLogger:
    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    def log_user_action(self, user_id: int, action: str, details: str = ""):
        """Логирование действий пользователя (5.1)."""
        logger.info(f"[USER:{user_id}] {action}: {details}")
        # TODO: Добавить запись в таблицу PostgreSQL 'logs'

    def log_error(self, error: Exception, component: str = "", details: str = ""):
        """Логирование ошибок и исключений (5.1)."""
        logger.error(f"[ERROR:{component}] {error}: {details}")

    def log_info(self, message: str, component: str = "", details: str = ""):
        """Логирование информационных сообщений."""
        logger.info(f"[{component}] {message}: {details}")

    def log_campaign_change(self, campaign_id: int, change: str, user_id: int):
        """Логирование изменений в кампаниях (5.1)."""
        logger.info(f"[CAMPAIGN:{campaign_id}] User {user_id} - Change: {change}")

bot_logger = BotLogger()
