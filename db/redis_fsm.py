# db/redis_fsm.py
from redis.asyncio.client import Redis
from aiogram.fsm.storage.redis import RedisStorage
from config import conf

# Создаем клиент Redis с параметрами из config.py
redis_client = Redis(
    host=conf.redis.host,
    port=conf.redis.port,
    decode_responses=True # Декодировать ответы, чтобы получать строки
)

# Создаем хранилище FSM
storage = RedisStorage(redis=redis_client)
