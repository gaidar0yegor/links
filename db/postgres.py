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

    # Таблица для очереди продуктов (упрощенная система качества)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS product_queue (
            id SERIAL PRIMARY KEY,
            campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
            asin TEXT NOT NULL,
            title TEXT,
            price DECIMAL(10,2),
            currency VARCHAR(3) DEFAULT 'USD',
            rating DECIMAL(3,2),
            review_count INTEGER,
            sales_rank INTEGER,
            image_url TEXT,
            affiliate_link TEXT,
            browse_node_ids INTEGER[] DEFAULT '{}',
            quality_score INTEGER, -- Sales rank as quality score (lower = better)
            status VARCHAR(20) DEFAULT 'queued', -- 'queued', 'posted', 'rejected'
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            posted_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Миграция: добавляем колонки, если их нет, для обратной совместимости
    await conn.execute("ALTER TABLE product_queue ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
    await conn.execute("ALTER TABLE product_queue ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP;")
    await conn.execute("ALTER TABLE product_queue ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")

    # Индексы для производительности
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_queue_campaign_status
        ON product_queue(campaign_id, status);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_queue_discovered
        ON product_queue(discovered_at);
    """)

    print("✅ Базовые таблицы PostgreSQL созданы или уже существуют.")

# connect_to_db и setup_db можно удалить или изменить для использования пула
# (Как показано выше)
