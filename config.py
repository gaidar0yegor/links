# config.py
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

@dataclass
class DbConfig:
    """Конфигурация для PostgreSQL"""
    host: str = os.getenv("DB_HOST", "localhost")
    user: str = os.getenv("DB_USER", "user")
    password: str = os.getenv("DB_PASS", "password")
    name: str = os.getenv("DB_NAME", "campaign_db")

@dataclass
class RedisConfig:
    """Конфигурация для Redis"""
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", 6379))

@dataclass
class GSheetsConfig:
    """Конфигурация для Google Sheets"""
    # ID вашего Google Sheets документа
    spreadsheet_id: str = os.getenv("SPREADSHEET_ID")
    # Путь к файлу ключей сервисного аккаунта для авторизации (Service Account)
    service_account_file: str = os.getenv("SERVICE_ACCOUNT_FILE", "keys.json")

@dataclass
class AmazonConfig:
    """Конфигурация для Amazon PA API 5.0"""
    access_key: str = os.getenv("AMAZON_ACCESS_KEY")
    secret_key: str = os.getenv("AMAZON_SECRET_KEY")
    associate_tag: str = os.getenv("AMAZON_ASSOCIATE_TAG")
    region: str = os.getenv("AMAZON_REGION", "eu-west-1")
    marketplace: str = os.getenv("AMAZON_MARKETPLACE", "amazon.it")
    use_api: bool = os.getenv("AMAZON_USE_API", "true").lower() in ("true", "1", "yes", "on")

@dataclass
class LLMConfig:
    """Конфигурация для LLM сервиса (Gemini API)"""
    api_key: str = os.getenv("GEMINI_API_KEY")
    model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

@dataclass
class Config:
    """Общая конфигурация приложения"""
    bot_token: str = os.getenv("BOT_TOKEN")
    db: DbConfig = field(default_factory=DbConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    gsheets: GSheetsConfig = field(default_factory=GSheetsConfig)
    amazon: AmazonConfig = field(default_factory=AmazonConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

# Инициализация объекта конфигурации
conf = Config()
