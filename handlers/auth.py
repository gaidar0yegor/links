# handlers/auth.py
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from services.sheets_api import sheets_api
from keyboards.main_menu import main_menu_keyboard

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Получаем Telegram ID пользователя
    user_id = message.from_user.id
    username = message.from_user.username or "No username"

    print(f"🔍 User access attempt - ID: {user_id}, Username: @{username}")

    # Загружаем whitelist
    authorized_ids = sheets_api.get_whitelist()
    print(f"📋 Current whitelist: {authorized_ids}")

    if user_id in authorized_ids:
        # Успешная авторизация
        print(f"✅ User {user_id} (@{username}) authorized successfully")
        await message.answer(
            "🎉 **Добро пожаловать в Affiliate Marketing Bot!**\n\n"
            "🤖 **Amazon Affiliate Marketing System**\n"
            "💰 Автоматизированная генерация дохода от партнерских ссылок\n\n"
            "✅ Авторизация успешна! Выберите действие в главном меню:",
            reply_markup=main_menu_keyboard()
        )

        # Сброс состояния для гарантии корректной работы главного меню
        await state.clear()
    else:
        # Отказ в доступе
        print(f"❌ User {user_id} (@{username}) access denied - not in whitelist")
        await message.answer(
            f"❌ Извините, ваш Telegram ID ({user_id}) не найден в списке авторизованных пользователей. Доступ запрещен."
        )

# Функция-фильтр для использования в других хэндлерах (опционально, но полезно)
async def is_whitelisted(user_id: int) -> bool:
    """Проверяет, авторизован ли пользователь."""
    return user_id in sheets_api.get_whitelist()
