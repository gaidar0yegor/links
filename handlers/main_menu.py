# handlers/main_menu.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
# from handlers.auth import is_whitelisted # Понадобится позже как фильтр

router = Router()

# Определение CallbackData для кнопок меню
class MainMenuCallback:
    CAMPAIGNS = "campaigns_module"
    STATS = "stats_module"

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Генерирует клавиатуру главного меню."""
    buttons = [
        [InlineKeyboardButton(text="1. Рекламные кампании", callback_data=MainMenuCallback.CAMPAIGNS)],
        [InlineKeyboardButton(text="2. Статистика", callback_data=MainMenuCallback.STATS)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def show_main_menu(message: Message | CallbackQuery, text: str = "Что вас интересует?") -> None:
    """Отображает главное меню."""
    if isinstance(message, Message):
        await message.answer(text, reply_markup=get_main_menu_keyboard())
    else: # Если это CallbackQuery, редактируем предыдущее сообщение
        await message.message.edit_text(text, reply_markup=get_main_menu_keyboard())


# Хэндлер для перехода в меню после успешного старта/авторизации
# Мы также регистрируем его как команду /menu для удобства
@router.message(Command("menu"))
@router.callback_query(F.data == "back_to_main_menu") # Кнопка "назад" из других модулей
async def main_menu_entry(update: Message | CallbackQuery):
    # TODO: Добавить проверку is_whitelisted, если нужно
    await show_main_menu(update)
    if isinstance(update, CallbackQuery):
        await update.answer() # Скрываем "часики"

# Тестовый хендлер для сообщений
@router.message(F.text == "test")
async def test_message_handler(message: Message):
    print("🔥 DEBUG: Test message handler called")
    await message.answer("Test message received!")

# Тестовый хендлер для кнопки кампаний
@router.callback_query(F.data == "campaigns_module")
async def test_campaigns_handler(callback_query: CallbackQuery, state):
    print(f"🔥 DEBUG: Campaigns button clicked: {callback_query.data}")
    await callback_query.answer("Кнопка кампаний работает!", show_alert=True)
    # Импортируем функцию из модуля кампаний
    from handlers.campaigns.manage import enter_campaign_module
    await enter_campaign_module(callback_query, state)

# Тестовый хендлер для кнопки статистики
@router.callback_query(F.data == "stats_module")
async def test_stats_handler(callback_query: CallbackQuery):
    print(f"🔥 DEBUG: Stats button clicked: {callback_query.data}")
    await callback_query.answer("Кнопка статистики работает!", show_alert=True)
    # Импортируем функцию из модуля статистики
    from handlers.statistics.stats import enter_stats_module
    await enter_stats_module(callback_query)

# Catch-all handler removed to prevent interference with campaign callbacks
