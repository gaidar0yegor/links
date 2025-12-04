# main.py
import asyncio
from aiogram import Bot, Dispatcher
from config import conf
from handlers import auth, main_menu # Импортируем новый роутер
from handlers.campaigns import campaigns_router # Импортируем сборный роутер
from db.redis_fsm import storage # Импортируем хранилище
from db.postgres import init_db_pool # Используем инициализацию пула
from services.campaign_manager import CampaignManager, set_campaign_manager
from services.scheduler import CampaignScheduler # Импортируем планировщик
from handlers.statistics import stats_router as stats # Импортируем роутер статистики

async def main():
    print("Инициализация инфраструктуры...")

    # Инициализация PostgreSQL Pool
    db_pool = await init_db_pool()
    if db_pool:
        # Инициализация CampaignManager с пулом
        campaign_manager_instance = CampaignManager(db_pool=db_pool)
        set_campaign_manager(campaign_manager_instance)

    # Инициализация Бота и Диспетчера с FSM Storage
    bot = Bot(token=conf.bot_token)
    dp = Dispatcher(storage=storage) # <--- Указываем Redis FSM Storage здесь
    print("🔥 DEBUG: Dispatcher created")
    
    # Передаём ссылку на бота в CampaignManager для уведомлений
    if db_pool:
        campaign_manager_instance.set_bot(bot)
        print("🔥 DEBUG: Bot reference set in CampaignManager")

    # Регистрация роутеров
    # auth.router должен перехватывать /start
    dp.include_router(auth.router)
    print("🔥 DEBUG: Registered auth.router")

    # main_menu.router должен перехватывать /menu и кнопки "назад"
    dp.include_router(main_menu.router)
    print("🔥 DEBUG: Registered main_menu.router")

    # Регистрируем основной роутер кампаний
    dp.include_router(campaigns_router)
    print("🔥 DEBUG: Registered campaigns_router")

    from handlers.statistics import stats_router
    dp.include_router(stats_router) # <--- Регистрируем роутер статистики
    print("🔥 DEBUG: Registered stats_router")

    # 4. Инициализация и запуск Планировщика
    if db_pool:
        # Передаем объекты, необходимые для работы Scheduler'а (Bot для постинга)
        from services.campaign_manager import campaign_manager
        print(f"🔧 Initializing scheduler with campaign_manager: {campaign_manager}")
        scheduler = CampaignScheduler(bot=bot, db_pool=db_pool, campaign_manager=campaign_manager)
        print(f"✅ Scheduler created: {scheduler.campaign_manager}")
        await scheduler.start()

    print("Запуск бота...")
    # Пропускаем накопившиеся обновления и запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
    except Exception as e:
        print(f"Критическая ошибка при запуске: {e}")
