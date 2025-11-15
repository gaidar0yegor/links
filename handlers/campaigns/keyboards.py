# handlers/campaigns/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple

def get_multiselect_keyboard(
    options: List[Tuple[str, str]], # [(Название, callback_value), ...]
    selected_values: List[str],
    done_callback: str,
    back_callback: str,
) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для мультивыбора."""
    buttons = []

    for name, value in options:
        # Индикатор выбора
        emoji = "☑️" if value in selected_values else "⬜️"
        # callback_data: "select_toggle:{value}"
        buttons.append([InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"select_toggle:{value}")])

    # Кнопки управления
    control_buttons = [
        # Кнопка "Выбрать все"
        InlineKeyboardButton(text="🔲 Выбрать все", callback_data="select_all_toggle"),
        # Кнопка "Готово"
        InlineKeyboardButton(text="✅ Готово", callback_data=done_callback),
    ]

    buttons.append(control_buttons)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
