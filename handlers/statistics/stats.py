# handlers/statistics/stats.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, Document
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from services.sheets_api import sheets_api

import pandas as pd
import io
from typing import Dict, List, Any

router = Router()

# --- Keyboards ---

def get_stats_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура модуля статистики."""
    buttons = [
        [InlineKeyboardButton(text="📤 Загрузить отчет о Кликах", callback_data="upload_report_clicks")],
        [InlineKeyboardButton(text="📤 Загрузить отчет о Продажах", callback_data="upload_report_sales")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены действия."""
    buttons = [
        [InlineKeyboardButton(text="⬅️ Отмена / Назад", callback_data="back_to_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Handlers ---

async def enter_stats_module(callback: CallbackQuery):
    """
    Вход в модуль статистики.
    Показывает инструкции и ссылки на дашборд.
    """
    dashboard_url = "https://docs.google.com/spreadsheets/d/1JCKM8hbfjdvuJIv8PzaORx5g4AKXdmzAiXhfjusO-_c/edit?gid=799923949#gid=799923949"
    clicks_stats_url = "https://docs.google.com/spreadsheets/d/1JCKM8hbfjdvuJIv8PzaORx5g4AKXdmzAiXhfjusO-_c/edit?gid=1240415011#gid=1240415011"

    text = (
        "<b>📊 Модуль Статистики</b>\n\n"
        "Для обновления данных на дашборде необходимо загрузить свежие отчеты из Amazon Associates.\n\n"
        "<b>🔗 Полезные ссылки:</b>\n"
        f"• <a href='{dashboard_url}'>Google Sheets Дашборд</a>\n"
        f"• <a href='{clicks_stats_url}'>Статистика Кликов</a>\n\n"
        "Выберите тип отчета для загрузки:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_stats_main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

# Handler for 'back_to_stats'
@router.callback_query(F.data == "back_to_stats")
async def back_to_stats_handler(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню статистики со сбросом состояния."""
    await state.clear()
    await enter_stats_module(callback)

# --- Upload Flows ---

@router.callback_query(F.data == "upload_report_clicks")
async def start_upload_clicks(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки отчета о кликах."""
    await state.set_state("waiting_for_clicks_csv")
    
    text = (
        "<b>📤 Загрузка отчета о КЛИКАХ</b>\n\n"
        "Пожалуйста, отправьте CSV файл с отчетом о кликах.\n"
        "Имя файла должно содержать <code>Tracking</code>.\n"
        "Выглядеть он должен так: 9374-Fee-Tracking.csv\n"
        "Данные будут записаны в лист <code>statistics_clicks</code>.\n\n"
        "<i>(Все старые данные в этом листе, кроме заголовков, будут удалены)</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "upload_report_sales")
async def start_upload_sales(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки отчета о продажах."""
    await state.set_state("waiting_for_sales_csv")
    
    text = (
        "<b>📤 Загрузка отчета о ПРОДАЖАХ (Orders)</b>\n\n"
        "Пожалуйста, отправьте CSV файл с отчетом о заказах/продажах.\n"
        "Имя файла должно содержать <code>Earnings</code>.\n"
        "Выглядеть он должен так: 9374-Earnings....csv\n"

        "Данные будут записаны в лист <code>statistics_orders</code>.\n\n"
        "<i>(Все старые данные в этом листе, кроме заголовков, будут удалены)</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard(), parse_mode="HTML")
    await callback.answer()

# --- File Processing ---

@router.message(StateFilter("waiting_for_clicks_csv"), F.document)
async def process_clicks_csv(message: Message, state: FSMContext):
    """Обработка CSV файла кликов."""
    # max_columns=6 (A-F)
    await process_csv_upload(message, state, "statistics_clicks", "Клики", "Tracking", max_columns=6)

@router.message(StateFilter("waiting_for_sales_csv"), F.document)
async def process_sales_csv(message: Message, state: FSMContext):
    """Обработка CSV файла продаж."""
    # max_columns=13 (A-M)
    await process_csv_upload(message, state, "statistics_orders", "Продажи", "Earnings", max_columns=13)

async def process_csv_upload(message: Message, state: FSMContext, target_sheet: str, report_name: str, required_filename_part: str, max_columns: int = None):
    """Общая логика обработки загрузки CSV."""
    
    # Проверка типа файла
    if not (message.document.mime_type == "text/csv" or message.document.file_name.lower().endswith(".csv")):
        await message.answer("❌ Пожалуйста, загрузите файл в формате CSV.")
        return

    # Проверка имени файла
    if required_filename_part not in message.document.file_name:
        await message.answer(
            f"❌ Неверный файл для отчета '{report_name}'.\n"
            f"Имя файла должно содержать <code>{required_filename_part}</code>.\n"
            f"Вы загрузили: <code>{message.document.file_name}</code>",
            parse_mode="HTML"
        )
        return

    status_msg = await message.answer("⏳ Загрузка и обработка файла...")

    try:
        # Скачивание файла
        file_info = await message.bot.get_file(message.document.file_id)
        file_content = await message.bot.download_file(file_info.file_path)
        
        # Чтение CSV
        csv_data = file_content.read().decode('utf-8')
        
        # Загрузка в Google Sheets
        success = sheets_api.upload_csv_to_sheet(target_sheet, csv_data, max_columns=max_columns)
        
        if success:
            await status_msg.delete()
            await message.answer(
                f"✅ <b>Отчет '{report_name}' успешно загружен!</b>\n"
                f"Данные обновлены в таблице <code>{target_sheet}</code>.",
                reply_markup=get_stats_main_keyboard(),
                parse_mode="HTML"
            )
            await state.clear()
        else:
            await status_msg.edit_text(
                "❌ Ошибка при загрузке в Google Sheets.\n"
                "Проверьте логи или доступность API."
            )
            
    except Exception as e:
        print(f"Error processing CSV upload: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка при обработке файла: {str(e)}")
        # Не сбрасываем состояние, даем попробовать еще раз

# Обработчик текстовых сообщений (если пользователь прислал текст вместо файла)
@router.message(StateFilter("waiting_for_clicks_csv", "waiting_for_sales_csv"), F.text)
async def handle_text_instead_of_file(message: Message):
    await message.answer("Пожалуйста, отправьте файл CSV, а не текст.", reply_markup=get_cancel_keyboard())
