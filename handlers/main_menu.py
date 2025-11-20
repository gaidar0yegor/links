# handlers/main_menu.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import main_menu_keyboard
# from handlers.auth import is_whitelisted # Понадобится позже как фильтр

router = Router()

async def show_main_menu(message: Message | CallbackQuery, text: str = "🎉 <b>Добро пожаловать в Affiliate Marketing Bot!</b>\n\n🤖 <b>Amazon Affiliate Marketing System</b>\n💰 Автоматизированная генерация дохода от партнерских ссылок\n\n✅ Авторизация успешна! Выберите действие в главном меню:") -> None:
    """Отображает главное меню."""
    if isinstance(message, Message):
        await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    else: # Если это CallbackQuery, редактируем предыдущее сообщение
        await message.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


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
    await message.answer("Тестовое сообщение получено!")

# Handler for campaigns button
@router.callback_query(F.data == "campaigns_module")
async def campaigns_handler(callback_query: CallbackQuery, state: FSMContext):
    print(f"🎯 Affiliate Campaigns module accessed: {callback_query.data}")
    await callback_query.answer("🎯 Открываю Рекламные кампании...", show_alert=False)
    # Import function from campaigns module
    from handlers.campaigns.manage import enter_campaign_module
    await enter_campaign_module(callback_query, state)

# Handler for statistics button
@router.callback_query(F.data == "stats_module")
async def stats_handler(callback_query: CallbackQuery):
    print(f"📊 Revenue Analytics module accessed: {callback_query.data}")
    await callback_query.answer("📊 Открываю Статистику...", show_alert=False)
    # Import function from statistics module
    from handlers.statistics.stats import enter_stats_module
    await enter_stats_module(callback_query)

# Catch-all handler removed to prevent interference with campaign callbacks
