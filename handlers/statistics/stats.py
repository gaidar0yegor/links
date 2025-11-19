# handlers/statistics/stats.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, Document
from aiogram.fsm.context import FSMContext
from services.sheets_api import sheets_api

import pandas as pd
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any

router = Router()

def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для модуля статистики."""
    buttons = [
        [InlineKeyboardButton(text="📤 Upload CSV Report", callback_data="stats_upload_csv")],
        [InlineKeyboardButton(text="📊 View Analytics", callback_data="stats_view_analytics")],
        [InlineKeyboardButton(text="🔄 Refresh Data", callback_data="stats_refresh")],
        [InlineKeyboardButton(text="⬅️ Main Menu", callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_analytics_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора периода аналитики."""
    buttons = [
        [InlineKeyboardButton(text="📅 Last 7 Days", callback_data="analytics_period:7")],
        [InlineKeyboardButton(text="📅 Last 30 Days", callback_data="analytics_period:30")],
        [InlineKeyboardButton(text="📅 Last 90 Days", callback_data="analytics_period:90")],
        [InlineKeyboardButton(text="🎯 By Tracking ID", callback_data="analytics_tracking")],
        [InlineKeyboardButton(text="⬅️ Back to Stats", callback_data="back_to_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# REMOVED: Duplicate handler for MainMenuCallback.STATS
# This is now handled by handlers/main_menu.py to avoid conflicts

@router.callback_query(F.data == "stats_refresh")
async def refresh_stats(callback: CallbackQuery):
    """Обновляет и отображает статистику продаж."""
    print(f"🔄 Stats refresh requested")

    # Получение данных (предполагаем, что sheet 'statistics' содержит агрегированные данные)
    try:
        stats_data = sheets_api.get_sheet_data("statistics")
        print(f"📊 Retrieved {len(stats_data) if stats_data else 0} stats rows")
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        stats_data = []

    # Форматирование
    text = "**📊 Revenue Analytics**\n\n"
    if len(stats_data) > 1:
        headers = stats_data[0]
        latest_data = stats_data[1] # Берем, например, последнюю строку (общие данные)

        # Пример простого форматирования:
        text += f"📅 Last Update: {latest_data[0] if len(latest_data)>0 else 'N/A'}\n"
        text += f"💰 Total Revenue: {latest_data[1] if len(latest_data)>1 else 'N/A'}\n"
        text += f"🔗 Total Clicks: {latest_data[2] if len(latest_data)>2 else 'N/A'}\n"
        text += f"🛒 Total Sales: {latest_data[3] if len(latest_data)>3 else 'N/A'}\n"
        text += "\n*Data sourced from Google Sheets (statistics table)."
    else:
        text += "No data available. Please ensure the 'statistics' table is populated."

    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    await callback.answer("📊 Statistics refreshed!", show_alert=False)

async def enter_stats_module(callback: CallbackQuery):
    """Отображает статистику продаж (called from main_menu.py)."""
    print(f"📊 Stats module entered from main menu")

    # Получение данных (предполагаем, что sheet 'statistics' содержит агрегированные данные)
    try:
        stats_data = sheets_api.get_sheet_data("statistics")
        print(f"📊 Retrieved {len(stats_data) if stats_data else 0} stats rows")
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        stats_data = []

    # Форматирование
    text = "**📊 Revenue Analytics**\n\n"
    if len(stats_data) > 1:
        headers = stats_data[0]
        latest_data = stats_data[1] # Берем, например, последнюю строку (общие данные)

        # Пример простого форматирования:
        text += f"📅 Last Update: {latest_data[0] if len(latest_data)>0 else 'N/A'}\n"
        text += f"💰 Total Revenue: {latest_data[1] if len(latest_data)>1 else 'N/A'}\n"
        text += f"🔗 Total Clicks: {latest_data[2] if len(latest_data)>2 else 'N/A'}\n"
        text += f"🛒 Total Sales: {latest_data[3] if len(latest_data)>3 else 'N/A'}\n"
        text += "\n*Data sourced from Google Sheets (statistics table)."
    else:
        text += "No data available. Please ensure the 'statistics' table is populated."

    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    await callback.answer()

@router.callback_query(F.data == "stats_upload_csv")
async def request_csv_upload(callback: CallbackQuery, state: FSMContext):
    """Запрашивает загрузку CSV файла с отчетом продаж."""
    await state.set_state("waiting_for_csv")
    text = "**📤 Upload Amazon Sales Report**\n\n"
    text += "Please upload your Amazon affiliate sales report CSV file.\n"
    text += "The file should contain columns: Categoria, Prodotto, ASIN, Data, Quantità, Prezzo (€), Tipo di link, Tag, etc.\n\n"
    text += "Supported format: All_orders CSV from Amazon Associates\n\n"
    text += "⬅️ Use /menu to return to main menu"

    await callback.message.edit_text(text)
    await callback.answer("📤 Ready for CSV upload", show_alert=False)

@router.callback_query(F.data == "stats_view_analytics")
async def show_analytics_menu(callback: CallbackQuery):
    """Показывает меню аналитики с выбором периода."""
    text = "**📊 Revenue Analytics Dashboard**\n\n"
    text += "Choose your analytics view:\n\n"
    text += "📅 **Time-based:** Filter by date ranges\n"
    text += "🎯 **Tracking ID:** Filter by specific affiliate tags\n\n"
    text += "Select a period or filter option:"

    await callback.message.edit_text(text, reply_markup=get_analytics_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("analytics_period:"))
async def show_period_analytics(callback: CallbackQuery):
    """Показывает аналитику за выбранный период."""
    days = int(callback.data.split(":")[1])

    # Get data from stored CSV or Google Sheets
    analytics_data = await get_analytics_data(days=days)

    text = f"**📊 Analytics - Last {days} Days**\n\n"

    if analytics_data:
        text += f"💰 **Total Revenue:** €{analytics_data.get('total_revenue', 0):.2f}\n"
        text += f"🛒 **Total Orders:** {analytics_data.get('total_orders', 0)}\n"
        text += f"📦 **Total Items:** {analytics_data.get('total_items', 0)}\n"
        text += f"🎯 **Active Tracking IDs:** {analytics_data.get('active_tags', 0)}\n\n"

        # Top products
        top_products = analytics_data.get('top_products', [])
        if top_products:
            text += "**🏆 Top Products:**\n"
            for i, product in enumerate(top_products[:5], 1):
                text += f"{i}. {product.get('name', 'N/A')} (€{product.get('revenue', 0):.2f})\n"
    else:
        text += "No data available for this period.\nUpload a CSV report first."

    await callback.message.edit_text(text, reply_markup=get_analytics_keyboard())
    await callback.answer()

@router.callback_query(F.data == "analytics_tracking")
async def request_tracking_id_filter(callback: CallbackQuery, state: FSMContext):
    """Запрашивает Tracking ID для фильтрации."""
    await state.set_state("waiting_for_tracking_id")

    # Get available tracking IDs
    available_tags = await get_available_tracking_ids()

    text = "**🎯 Filter by Tracking ID**\n\n"
    if available_tags:
        text += "Available Tracking IDs:\n"
        for tag in available_tags[:10]:  # Show first 10
            text += f"• {tag}\n"
        text += "\n"
    text += "Enter a Tracking ID to filter analytics:"

    await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data == "back_to_stats")
async def back_to_stats_menu(callback: CallbackQuery):
    """Возвращает в главное меню статистики."""
    await enter_stats_module(callback)

@router.message(F.document, F.document.mime_type == "text/csv")
async def handle_csv_upload(message: Message, state: FSMContext):
    """Обрабатывает загруженный CSV файл."""
    try:
        # Check if we're waiting for CSV
        current_state = await state.get_state()
        if current_state != "waiting_for_csv":
            await message.answer("❌ Not expecting a CSV file right now. Use the statistics menu to upload reports.")
            return

        # Download the file
        file_info = await message.bot.get_file(message.document.file_id)
        file_content = await message.bot.download_file(file_info.file_path)

        # Parse CSV
        csv_data = file_content.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_data), sep=',', quotechar='"')

        # Process the data
        processed_data = await process_amazon_csv(df)

        # Store processed data (you might want to save to database or Google Sheets)
        await store_csv_data(processed_data)

        # Clear state
        await state.clear()

        # Show success message with summary
        summary = processed_data.get('summary', {})
        text = "**✅ CSV Report Processed Successfully!**\n\n"
        text += f"📊 **Report Summary:**\n"
        text += f"• Orders: {summary.get('total_orders', 0)}\n"
        text += f"• Revenue: €{summary.get('total_revenue', 0):.2f}\n"
        text += f"• Items: {summary.get('total_items', 0)}\n"
        text += f"• Date Range: {summary.get('date_range', 'N/A')}\n"
        text += f"• Tracking IDs: {summary.get('tracking_ids', 0)}\n\n"
        text += "Data has been stored and is available in analytics."

        await message.answer(text, reply_markup=get_stats_keyboard())

    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Error processing CSV file: {str(e)}\n\nPlease ensure it's a valid Amazon All_orders CSV file.")
        print(f"CSV processing error: {e}")

@router.message(F.text & ~F.document)
async def handle_tracking_id_input(message: Message, state: FSMContext):
    """Обрабатывает ввод Tracking ID для фильтрации."""
    current_state = await state.get_state()
    if current_state != "waiting_for_tracking_id":
        return

    tracking_id = message.text.strip()

    # Get analytics for specific tracking ID
    analytics_data = await get_analytics_data(tracking_id=tracking_id)

    await state.clear()

    text = f"**🎯 Analytics for Tracking ID: {tracking_id}**\n\n"

    if analytics_data:
        text += f"💰 **Revenue:** €{analytics_data.get('total_revenue', 0):.2f}\n"
        text += f"🛒 **Orders:** {analytics_data.get('total_orders', 0)}\n"
        text += f"📦 **Items:** {analytics_data.get('total_items', 0)}\n"
        text += f"📅 **Date Range:** {analytics_data.get('date_range', 'N/A')}\n\n"

        # Show top products for this tracking ID
        top_products = analytics_data.get('top_products', [])
        if top_products:
            text += "**🏆 Top Products:**\n"
            for i, product in enumerate(top_products[:5], 1):
                text += f"{i}. {product.get('name', 'N/A')} (€{product.get('revenue', 0):.2f})\n"
    else:
        text += f"No data found for Tracking ID '{tracking_id}'."

    await message.answer(text, reply_markup=get_analytics_keyboard())

# Helper functions for data processing

async def process_amazon_csv(df: pd.DataFrame) -> Dict[str, Any]:
    """Process Amazon All_orders CSV data."""
    try:
        # Expected columns from the CSV
        expected_cols = ['Categoria', 'Prodotto', 'ASIN', 'Data', 'Quantità', 'Prezzo (€)', 'Tipo di link', 'Tag']

        # Check if required columns exist
        missing_cols = [col for col in expected_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Convert Data column to datetime
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

        # Clean and convert price column
        df['Prezzo (€)'] = pd.to_numeric(df['Prezzo (€)'].astype(str).str.replace('€', '').str.replace(',', '.'), errors='coerce')

        # Clean quantity column
        df['Quantità'] = pd.to_numeric(df['Quantità'], errors='coerce')

        # Calculate summary statistics
        total_orders = len(df)
        total_revenue = df['Prezzo (€)'].sum()
        total_items = df['Quantità'].sum()
        date_range = f"{df['Data'].min().strftime('%Y-%m-%d')} to {df['Data'].max().strftime('%Y-%m-%d')}"
        tracking_ids = df['Tag'].nunique()

        # Top products by revenue
        product_revenue = df.groupby('Prodotto')['Prezzo (€)'].sum().reset_index()
        top_products = product_revenue.nlargest(10, 'Prezzo (€)').to_dict('records')

        # Convert to serializable format
        top_products_serialized = [
            {'name': prod['Prodotto'], 'revenue': float(prod['Prezzo (€)'])}
            for prod in top_products
        ]

        return {
            'summary': {
                'total_orders': int(total_orders),
                'total_revenue': float(total_revenue),
                'total_items': int(total_items),
                'date_range': date_range,
                'tracking_ids': int(tracking_ids)
            },
            'top_products': top_products_serialized,
            'raw_data': df.to_dict('records')
        }

    except Exception as e:
        raise ValueError(f"Error processing CSV: {str(e)}")

async def store_csv_data(data: Dict[str, Any]):
    """Store processed CSV data (placeholder - implement based on your storage needs)."""
    # This could save to database, Google Sheets, or file system
    # For now, we'll just print that data was processed
    print(f"📊 Stored CSV data: {data['summary']}")
    # TODO: Implement actual storage logic

async def get_analytics_data(days: int = None, tracking_id: str = None) -> Dict[str, Any]:
    """Get analytics data from stored CSV data."""
    # This is a placeholder - in real implementation, you'd query stored data
    # For now, return mock data
    return {
        'total_revenue': 1250.50,
        'total_orders': 45,
        'total_items': 67,
        'active_tags': 3,
        'date_range': f"Last {days} days" if days else "All time",
        'top_products': [
            {'name': 'Premium Product A', 'revenue': 450.00},
            {'name': 'Best Seller B', 'revenue': 320.50},
            {'name': 'Top Item C', 'revenue': 280.00}
        ]
    }

async def get_available_tracking_ids() -> List[str]:
    """Get list of available tracking IDs from stored data."""
    # This is a placeholder - in real implementation, you'd query stored data
    return ['tag1', 'tag2', 'tag3', 'ivestmente-21', 'lanotizia09-21']
