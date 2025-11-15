# keyboards/main_menu.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру для Главного меню (ТЗ 2.2)."""
    buttons = [
        [
            InlineKeyboardButton(text="Рекламные кампании", callback_data="campaigns_module")
        ],
        [
            InlineKeyboardButton(text="Статистика", callback_data="stats_module")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
