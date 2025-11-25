# services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from services.campaign_manager import CampaignManager, campaign_manager
from services.post_manager import PostManager
from services.amazon_paapi_client import AmazonPAAPIClient

class CampaignScheduler:
    """Управляет планировщиком задач (APScheduler) для автопостинга."""
    def __init__(self, bot, db_pool, campaign_manager):
        # Инициализируем планировщик
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        self.campaign_manager = campaign_manager
        self.post_manager = PostManager(bot=bot) # Инициализация PostManager

    async def start(self):
        """Запускает планировщик и регистрирует главную задачу."""

        # Главная задача: запускать цикл автопостинга каждую минуту
        # Это будет наш главный "тик" системы для ротации кампаний
        self.scheduler.add_job(
            self.main_posting_cycle,
            'interval',
            minutes=1,
            id='main_posting_cycle',
            replace_existing=True,
            misfire_grace_time=30 # Допускаем задержку в 30 секунд
        )

        # Дополнительная задача: обновление данных из Google Sheets (например, раз в час)
        self.scheduler.add_job(
            self.refresh_gsheets_data,
            'interval',
            hours=1,
            id='refresh_gsheets_data',
            replace_existing=True
        )

        # Новая задача: автоматическое обнаружение и очередь продуктов (каждые 6 часов)
        self.scheduler.add_job(
            self.product_discovery_cycle,
            'interval',
            hours=6,  # Changed from 12 to 6
            id='product_discovery_cycle',
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ Планировщик задач запущен.")

    async def main_posting_cycle(self):
        """Главный цикл, который проверяет тайминги, конфликты и запускает посты."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Запущен цикл автопостинга...")

        # 1. Получаем список активных кампаний
        active_campaigns = await self.campaign_manager.get_active_campaigns_with_timings()

        if not active_campaigns:
            print("Нет активных кампаний с заданным таймингом.")
            return

        # 2. Проверяем все активные кампании и запускаем те, которые соответствуют текущему времени
        current_time = datetime.now().time()
        current_day = datetime.now().weekday() # 0 = Пн, 6 = Вс

        campaigns_to_run = []

        # Находим все кампании, которые должны запуститься в текущий момент
        for campaign in active_campaigns:
            if self.is_posting_time(campaign, current_day, current_time):
                campaigns_to_run.append(campaign)

        if not campaigns_to_run:
            # TEMPORARY: Force run ALL active campaigns to test posting
            print(f"⏰ Нет кампаний для запуска по расписанию. Принудительно запускаем все активные кампании")
            campaigns_to_run = active_campaigns

        # 3. Запускаем все подходящие кампании (с учетом частоты постинга)
        for selected_campaign in campaigns_to_run:
            # Проверяем частоту постинга (posting frequency)
            posting_frequency = selected_campaign.get('posting_frequency', 0)  # posts per hour
            last_post_time = selected_campaign.get('last_post_time')

            if posting_frequency > 0 and last_post_time:
                # Вычисляем минимальный интервал между постами в секундах
                min_interval_seconds = (3600 / posting_frequency)  # seconds between posts

                # Проверяем, прошло ли достаточно времени с последнего поста
                time_since_last_post = (datetime.now() - last_post_time).total_seconds()

                if time_since_last_post < min_interval_seconds:
                    remaining_minutes = (min_interval_seconds - time_since_last_post) / 60
                    print(f"⏰ Кампания '{selected_campaign['name']}' - частота {posting_frequency} постов/час. "
                          f"Последний пост был {time_since_last_post:.0f} сек назад. "
                          f"Следующий пост через {remaining_minutes:.1f} мин.")
                    continue

                print(f"✅ Кампания '{selected_campaign['name']}' - прошедшее время {time_since_last_post:.0f} сек >= "
                      f"минимум {min_interval_seconds:.0f} сек. Разрешен пост.")

            # Проверяем, не постили ли мы уже в этом временном окне (legacy check)
            elif last_post_time:
                # Если последний пост был в текущем временном окне, пропускаем
                current_window_start = None
                for timing in selected_campaign.get('timings', []):
                    if timing['day_of_week'] == current_day and timing['start_time'] <= current_time < timing['end_time']:
                        current_window_start = datetime.combine(datetime.today(), timing['start_time'])
                        break

                if current_window_start and last_post_time >= current_window_start:
                    print(f"⏰ Кампания '{selected_campaign['name']}' уже постила в этом временном окне, пропускаем.")
                    continue

            print(f"-> Кампания '{selected_campaign['name']}' соответствует таймингу. Запуск постинга...")

            # 4. Попытка получить продукт из очереди
            queued_product = await self.campaign_manager.get_next_queued_product(selected_campaign['id'])

            if queued_product:
                print(f"📦 Используем продукт из очереди: {queued_product['asin']} - {queued_product['title'][:50]}...")

                # Use the new format expected by post_queued_product
                product_data_for_post = {
                    'asin': queued_product['asin'],
                    'Title': queued_product['title'],
                    'price': queued_product['price'],
                    'currency': queued_product['currency'],
                    'rating': queued_product['rating'],
                    'review_count': queued_product['review_count'],
                    'sales_rank': queued_product['sales_rank'],
                    'image_urls': queued_product['image_urls'],
                    'affiliate_link': queued_product['affiliate_link'],
                    'features': queued_product['features'],
                    'description': '' # Description is generated from features if needed
                }

                # Запуск постинга с продуктом из очереди
                await self.post_manager.post_queued_product(selected_campaign, product_data_for_post)

                # Отмечаем продукт как опубликованный
                await self.campaign_manager.mark_product_posted(queued_product['id'])

                print(f"✅ Продукт из очереди опубликован: {queued_product['asin']}")

            else:
                print(f"📭 Очередь пуста для кампании '{selected_campaign['name']}'. Используем поиск в реальном времени...")

                # 4b. Fallback: Запуск основного процесса постинга (поиск в реальном времени)
                await self.post_manager.fetch_and_post_enhanced(selected_campaign)

            # 5. Обновление времени последнего поста
            await self.campaign_manager.mark_last_post_time(selected_campaign['id'], datetime.now())

    def check_timing_conflict(self, current_campaign) -> bool:
        """
        Проверяет, нет ли конфликта с другой ОДНОВРЕМЕННО запущенной кампанией
        в одном и том же канале (Требование 2.6).

        ВНИМАНИЕ: Проверку конфликтов нужно делать в CampaignManager,
        на уровне БД, чтобы исключить запуск двух кампаний в одном канале.

        Здесь мы делаем упрощенную проверку (будет исправлено на Шаге 10).
        """
        # Пока просто пропускаем
        return True # Временное решение

    def is_posting_time(self, campaign, current_day, current_time) -> bool:
        """Проверяет, соответствует ли текущее время таймингу кампании."""
        for timing in campaign.get('timings', []):
            # Проверяем день
            # Support for daily schedules: if day_of_week is None or negative, treat as daily
            timing_day = timing.get('day_of_week')
            if timing_day is None or timing_day < 0 or timing_day == current_day:
                # Проверяем, находится ли текущее время в интервале [start_time, end_time)
                start = timing['start_time']
                end = timing['end_time']

                # Постинг происходит в течение всего интервала
                if start <= current_time < end:
                    return True
        return False

    async def process_campaign_posting(self, campaign):
        """Заглушка для основного процесса постинга."""
        # Здесь будет логика: API запрос -> Рерайт -> Постинг
        print(f"Постинг для {campaign['name']} в каналы: {campaign['params']['channels']}")
        # await self.bot.send_message(CHAT_ID, f"Запущен пост для {campaign['name']}")

    async def product_discovery_cycle(self):
        """Автоматическое обнаружение и добавление продуктов в очередь."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Запущен цикл обнаружения продуктов...")

        # Инициализируем Amazon PA API клиент
        amazon_client = AmazonPAAPIClient()

        # Получаем все активные кампании
        active_campaigns = await self.campaign_manager.get_active_campaigns_with_timings()

        if not active_campaigns:
            print("❌ Нет активных кампаний для обнаружения продуктов.")
            return

        total_queued = 0

        for campaign in active_campaigns:
            campaign_id = campaign['id']
            campaign_name = campaign['name']
            params = campaign.get('params', {})

            # Проверяем размер очереди для этой кампании
            queue_size = await self.campaign_manager.get_queue_size(campaign_id)
            print(f"📊 Кампания '{campaign_name}' (ID: {campaign_id}): очередь содержит {queue_size} продуктов")

            # Если очередь достаточно большая (минимум 20 продуктов), пропускаем
            if queue_size >= 20:
                print(f"⏭️  Кампания '{campaign_name}': очередь достаточно полная, пропускаем")
                continue

            # Определяем параметры поиска
            browse_node_ids = params.get('browse_node_ids', [])
            min_rating = params.get('min_rating', 0.0)
            min_price = params.get('min_price')
            fulfilled_by_amazon = params.get('fulfilled_by_amazon')
            # Get campaign-specific sales rank threshold (simplified quality control)
            max_sales_rank = params.get('max_sales_rank', 10000)

            if not browse_node_ids:
                print(f"⚠️  Кампания '{campaign_name}': нет browse_node_ids, пропускаем")
                continue

            print(f"🔎 Поиск продуктов для кампании '{campaign_name}' в категориях: {browse_node_ids} (max rank: {max_sales_rank})")

            try:
                # Get already queued/posted ASINs to avoid duplicates
                posted_asins = await self.campaign_manager.get_posted_asins(campaign_id, limit=5000)

                # Выполняем поиск продуктов
                search_results = await amazon_client.search_items_enhanced(
                    browse_node_ids=browse_node_ids,
                    min_rating=min_rating,
                    min_price=min_price,
                    fulfilled_by_amazon=fulfilled_by_amazon,
                    max_results=50  # Increased from 10 to 50 to find more new products
                )

                if not search_results:
                    print(f"❌ Кампания '{campaign_name}': продукты не найдены")
                    continue

                queued_for_campaign = 0

                # Обрабатываем каждый найденный продукт
                for product in search_results:
                    # Skip if already posted or queued
                    if product.get('asin') in posted_asins:
                        continue
                    # Применяем фильтр по sales rank (единственный критерий качества)
                    sales_rank = product.get('sales_rank')
                    if sales_rank is None or sales_rank > max_sales_rank:
                        continue  # Пропускаем продукты с низким рейтингом продаж

                    # Подготавливаем данные для очереди
                    product_data = {
                        'asin': product['asin'],
                        'title': product.get('title'),
                        'price': product.get('price'),
                        'currency': product.get('currency', 'USD'),
                        'rating': product.get('rating'),
                        'review_count': product.get('review_count'),
                        'sales_rank': sales_rank,
                        'image_url': product.get('image_url'),
                        'affiliate_link': product.get('affiliate_link'),
                        'browse_node_ids': browse_node_ids
                    }

                    # Добавляем продукт в очередь
                    try:
                        product_id = await self.campaign_manager.add_product_to_queue(campaign_id, product_data)
                        queued_for_campaign += 1
                        total_queued += 1
                        print(f"✅ Добавлен продукт {product['asin']} (rank: {sales_rank}) в очередь кампании '{campaign_name}'")
                    except Exception as e:
                        print(f"❌ Ошибка добавления продукта {product['asin']}: {e}")
                        continue

                print(f"📈 Кампания '{campaign_name}': добавлено {queued_for_campaign} продуктов в очередь")

            except Exception as e:
                print(f"❌ Ошибка поиска для кампании '{campaign_name}': {e}")
                continue

        # Очистка старых продуктов (старше 30 дней)
        try:
            cleaned_count = await self.campaign_manager.cleanup_old_products(days=30)
            if cleaned_count > 0:
                print(f"🧹 Очищено {cleaned_count} старых продуктов из очереди")
        except Exception as e:
            print(f"❌ Ошибка очистки: {e}")

        print(f"🎉 Цикл обнаружения завершен. Всего добавлено в очередь: {total_queued} продуктов")

    async def refresh_gsheets_data(self):
        """Обновляет кэш данных из Google Sheets (например, whitelist, категории)."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Обновление данных из Google Sheets...")
        # TODO: Добавить логику в sheets_api, чтобы он кэшировал данные в PostgreSQL.
        # Например, sheets_api.refresh_all_cache()
