# db/postgres.py
import asyncpg
from config import conf

# Глобальная переменная для пула
db_pool: asyncpg.pool.Pool | None = None

async def init_db_pool():
    """Инициализирует пул соединений PostgreSQL."""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            user=conf.db.user,
            password=conf.db.password,
            database=conf.db.name,
            host=conf.db.host,
            min_size=5,  # Минимальное количество соединений в пуле
            max_size=10  # Максимальное количество
        )
        print("✅ Успешное создание пула PostgreSQL.")
        # Вызываем setup_db для создания таблиц, используя соединение из пула
        async with db_pool.acquire() as conn:
            await setup_db(conn)

        return db_pool
    except Exception as e:
        print(f"❌ Ошибка инициализации пула PostgreSQL: {e}")
        return None

async def setup_db(conn):
    """Создает необходимые таблицы при первом запуске."""
    if conn is None:
        print("Невозможно создать таблицы: соединение с БД отсутствует.")
        return

    # Таблица для активных кампаний (требование 3. campaigns)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            status VARCHAR(50) NOT NULL, -- 'running', 'stopped', 'timingless'
            params JSONB NOT NULL, -- Храним все параметры (категории, рейтинг и т.д.)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_post_time TIMESTAMP -- Время последнего поста (для предотвращения повторного постинга)
        );
    """)

    # Таблица для расписания/таймингов (для проверки конфликтов)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_timings (
            campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
            day_of_week INTEGER NOT NULL, -- 0=Пн, 6=Вс
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            PRIMARY KEY (campaign_id, day_of_week, start_time)
        );
    """)

    # Таблица для логирования статистики постов (ТЗ 3.2)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS statistics_log (
            id SERIAL PRIMARY KEY,
            campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
            channel_name TEXT NOT NULL,
            post_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            asin TEXT,
            final_link TEXT NOT NULL
        );
    """)

    print("✅ Базовые таблицы PostgreSQL созданы или уже существуют.")

# connect_to_db и setup_db можно удалить или изменить для использования пула
# (Как показано выше)
