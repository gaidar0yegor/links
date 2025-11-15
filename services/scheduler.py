# services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from services.campaign_manager import CampaignManager, campaign_manager
from services.post_manager import PostManager

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
        # Это будет наш главный "тик" системы
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

        # 2. Проверка текущего времени и таймингов
        current_time_str = datetime.now().strftime("%H:%M")
        current_time = datetime.now().time()
        current_day = datetime.now().weekday() # 0 = Пн, 6 = Вс

        for campaign in active_campaigns:
            # 3. Проверка конфликтов (2.6)
            conflicting_channels = await self.campaign_manager.get_conflicting_campaigns(
                campaign['id'],
                current_day,
                current_time_str
            )

            if conflicting_channels:
                print(f"⚠️ КОНФЛИКТ: Кампания '{campaign['name']}' конфликтует в каналах: {conflicting_channels}. Постинг отменен.")
                continue

            # 4. Проверка на соответствие текущему дню и времени
            if self.is_posting_time(campaign, current_day, current_time):
                print(f"-> Кампания '{campaign['name']}' соответствует таймингу. Запуск постинга...")

                # 5. Запуск основного процесса постинга
                await self.post_manager.fetch_and_post(campaign)

                # 6. Обновление времени последнего поста
                await self.campaign_manager.mark_last_post_time(campaign['id'], datetime.now())

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
            if timing['day_of_week'] == current_day:
                # Проверяем, находится ли текущее время в интервале [start_time, end_time)
                start = datetime.strptime(timing['start_time'], "%H:%M:%S").time()
                end = datetime.strptime(timing['end_time'], "%H:%M:%S").time()

                # Постинг должен произойти один раз в начале интервала или в течение него
                # Для простоты, допустим, мы постим, если время находится в интервале
                if start <= current_time < end:
                     # TODO: Реализовать логику, чтобы пост был один раз в интервале!
                    return True
        return False

    async def process_campaign_posting(self, campaign):
        """Заглушка для основного процесса постинга."""
        # Здесь будет логика: API запрос -> Рерайт -> Постинг
        print(f"Постинг для {campaign['name']} в каналы: {campaign['params']['channels']}")
        # await self.bot.send_message(CHAT_ID, f"Запущен пост для {campaign['name']}")

    async def refresh_gsheets_data(self):
        """Обновляет кэш данных из Google Sheets (например, whitelist, категории)."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Обновление данных из Google Sheets...")
        # TODO: Добавить логику в sheets_api, чтобы он кэшировал данные в PostgreSQL.
        # Например, sheets_api.refresh_all_cache()
