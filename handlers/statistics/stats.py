# handlers/statistics/stats.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.sheets_api import sheets_api
from handlers.main_menu import MainMenuCallback

router = Router()

def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для модуля статистики."""
    buttons = [
        # Тут могут быть кнопки для выбора периода, типа отчета и т.д.
        [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="stats_refresh")],
        [InlineKeyboardButton(text="⬅️ В Главное меню", callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data == MainMenuCallback.STATS)
@router.callback_query(F.data == "stats_refresh")
async def enter_stats_module(callback: CallbackQuery):
    """Отображает статистику продаж, выгруженную из Google Sheets (требование 2.2)."""
    print(f"🔥 DEBUG: enter_stats_module called with data: {callback.data}")

    # TODO: В идеале, данные должны кэшироваться в PostgreSQL (см. 3.2 statistics)

    # 1. Получение данных (предполагаем, что sheet 'statistics' содержит агрегированные данные)
    try:
        stats_data = sheets_api.get_sheet_data("statistics")
        print(f"🔥 DEBUG: Got stats data: {len(stats_data) if stats_data else 0} rows")
    except Exception as e:
        print(f"🔥 DEBUG: Error getting stats: {e}")
        stats_data = []

    # 2. Форматирование
    text = "**📊 Общая Статистика Продаж**\n\n"
    if len(stats_data) > 1:
        headers = stats_data[0]
        latest_data = stats_data[1] # Берем, например, последнюю строку (общие данные)

        # Пример простого форматирования:
        text += f"📅 Последнее обновление: {latest_data[0] if len(latest_data)>0 else 'Н/Д'}\n"
        text += f"💰 Общий доход: {latest_data[1] if len(latest_data)>1 else 'Н/Д'}\n"
        text += f"🔗 Всего кликов: {latest_data[2] if len(latest_data)>2 else 'Н/Д'}\n"
        text += f"🛒 Всего продаж: {latest_data[3] if len(latest_data)>3 else 'Н/Д'}\n"
        text += "\n*Данные выгружены из Google Sheets (таблица statistics)."
    else:
        text += "Нет данных для отображения. Убедитесь, что таблица 'statistics' заполнена."

    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    await callback.answer()
