# handlers/campaigns/manage.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from typing import List, Optional
from services.campaign_manager import get_campaign_manager
from states.campaign_states import CampaignStates
from services.logger import bot_logger
from datetime import datetime, time
from handlers.campaigns.keyboards import get_multiselect_keyboard

router = Router()

def get_campaign_menu_keyboard(campaigns: list) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру меню кампаний, включая список существующих."""
    buttons = []

    # 1. Создать новую кампанию (Требование 2.3.1)
    buttons.append([InlineKeyboardButton(text="➕ Создать новую кампанию", callback_data="campaign_new_start")])

    # 2. Список существующих кампаний (Требование 2.3.1)
    if campaigns:
        buttons.append([InlineKeyboardButton(text="⬇️ Редактировать существующую ⬇️", callback_data="ignore")])
        for camp in campaigns:
            # Отображение названия и статуса
            status_emoji = "🟢" if camp['db_status'] == 'running' else "🔴"
            if camp['status'] == 'Не выбраны тайминги':
                 status_emoji = "🟡"

            text = f"{status_emoji} {camp['name']} ({camp['status']})"
            # data: "campaign_edit:{campaign_id}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=f"campaign_edit:{camp['id']}")])

    # Кнопка "Назад" (Требование 4.3)
    buttons.append([InlineKeyboardButton(text="⬅️ В Главное меню", callback_data="back_to_main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_campaign_edit_keyboard(campaign_id: int, current_status: str) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для редактирования/управления кампанией."""

    # Кнопки управления статусом (2.5)
    if current_status == 'running':
        status_button = InlineKeyboardButton(text="⏸ Остановить кампанию", callback_data=f"campaign_status:stop:{campaign_id}")
    else:
        status_button = InlineKeyboardButton(text="▶️ Запустить кампанию", callback_data=f"campaign_status:run:{campaign_id}")

    buttons = [
        [status_button],
        # MODIFIED: Points to the new multi-select timing handler
        [InlineKeyboardButton(text="⏰ Установить/Изменить тайминги (2.4)", callback_data=f"campaign_edit_timings:{campaign_id}")],
        # MODIFIED: Points to the new delete confirmation handler
        [InlineKeyboardButton(text="🗑 Удалить кампанию", callback_data=f"campaign_delete_confirm:{campaign_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_campaign_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS_MAPPING = {i: day for i, day in enumerate(DAYS)} # 0: "Пн", 1: "Вт" и т.д.

# REMOVED: Old single-day selection keyboard function `get_day_select_keyboard`


# REMOVED: Duplicate handler for MainMenuCallback.CAMPAIGNS
# This is now handled by handlers/main_menu.py to avoid conflicts

async def enter_campaign_module(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает вход в модуль 'Рекламные кампании'."""
    print(f"🎯 Campaign module entered from main menu")

    await state.set_state(CampaignStates.in_campaign_menu)

    # Получаем список кампаний из БД
    try:
        campaign_mgr = get_campaign_manager()
        if campaign_mgr is None:
            print("❌ campaign_manager is None")
            campaigns = []
        else:
            campaigns = await campaign_mgr.get_all_campaigns_summary()
            print(f"📊 Retrieved {len(campaigns)} campaigns")
            if campaigns:
                print(f"📋 First campaign: {campaigns[0]}")
                for i, camp in enumerate(campaigns):
                    print(f"📋 Campaign {i+1}: ID={camp['id']}, Name='{camp['name']}', Status='{camp['status']}'")
            else:
                print("📋 No campaigns retrieved")
    except Exception as e:
        print(f"❌ Error getting campaigns: {e}")
        import traceback
        traceback.print_exc()
        campaigns = []

    text = "**🎯 Affiliate Campaigns Management**\n\nChoose an operation or select a campaign to edit:"

    keyboard = get_campaign_menu_keyboard(campaigns)
    print(f"⌨️ Generated keyboard with {len(keyboard.inline_keyboard)} buttons")

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("campaign_edit:"))
async def enter_campaign_edit_menu(callback: CallbackQuery, state: FSMContext):
    """Открывает меню редактирования/управления конкретной кампанией."""

    print(f"🎯 Campaign edit clicked: {callback.data}")

    # Извлекаем ID кампании
    try:
        campaign_id = int(callback.data.split(":")[1])
        print(f"📋 Extracted campaign ID: {campaign_id}")
    except (ValueError, IndexError) as e:
        print(f"❌ Error parsing campaign ID from {callback.data}: {e}")
        await callback.answer("❌ Invalid campaign ID", show_alert=True)
        return

    # TODO: Получить полные данные кампании из БД
    campaign_mgr = get_campaign_manager()
    campaign = await campaign_mgr.get_campaign_details(campaign_id) if campaign_mgr else None

    if not campaign:
        await callback.answer("❌ Кампания не найдена.", show_alert=True)
        await enter_campaign_module(callback, state) # Вернуться в главное меню кампаний
        return

    await state.set_state(CampaignStates.campaign_edit_main)
    # Сохраняем ID для последующих операций
    await state.set_data({'current_campaign_id': campaign_id})

    # Формируем текст с деталями и текущим статусом
    status_emoji = "🟢" if campaign['status'] == 'running' else ("🔴" if campaign['status'] == 'stopped' else "🟡")

    text = (
        f"**Управление кампанией: {campaign['name']}**\n\n"
        f"Текущий статус: **{status_emoji} {campaign['status']}**\n"
        f"Мин. рейтинг: {campaign['params'].get('min_rating', 'Не задан')}\n"
        # TODO: Добавить отображение текущих таймингов
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_campaign_edit_keyboard(campaign_id, campaign['status'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("campaign_status:"))
async def toggle_campaign_status(callback: CallbackQuery, state: FSMContext):
    """Запуск или остановка кампании (2.5)."""
    _, action, campaign_id_str = callback.data.split(":")
    campaign_id = int(campaign_id_str)

    # 1. Проверяем, можно ли запустить (только если есть тайминги)
    campaign_mgr = get_campaign_manager()
    if action == 'run' and campaign_mgr:
        has_timings = await campaign_mgr.has_timings(campaign_id)
        if not has_timings:
            await callback.answer("⚠️ Невозможно запустить! Сначала установите тайминги (2.4).", show_alert=True)
            # Переоткрываем меню, чтобы пользователь увидел кнопку таймингов
            await enter_campaign_edit_menu(callback, state)
            return

    # 2. Обновляем статус в БД
    if campaign_mgr:
        new_status = 'running' if action == 'run' else 'stopped'
        await campaign_mgr.update_status(campaign_id, new_status)

    await callback.answer(f"Кампания {'запущена' if action == 'run' else 'остановлена'}.", show_alert=True)

    # Возвращаемся в меню редактирования для обновления UI
    await enter_campaign_edit_menu(callback, state)

# --- NEW MULTI-SELECT TIMING WORKFLOW ---

@router.callback_query(F.data.startswith("campaign_edit_timings:"))
async def edit_campaign_timings_handler(callback: CallbackQuery, state: FSMContext):
    """Handler for 'Edit Timings' button, starts the multi-select flow."""
    campaign_id = int(callback.data.split(":")[1])
    await edit_campaign_timings(callback, state, campaign_id)

async def edit_campaign_timings(query_or_message: CallbackQuery | Message, state: FSMContext, campaign_id: int):
    """Displays the timing management menu for a campaign with multi-select for days."""
    message = query_or_message.message if isinstance(query_or_message, CallbackQuery) else query_or_message

    campaign_mgr = get_campaign_manager()
    campaign = await campaign_mgr.get_campaign_details(campaign_id)
    if not campaign:
        await message.answer("❌ Кампания не найдена.")
        return

    campaign_name = campaign['name']
    timings_list = await campaign_mgr.get_timings(campaign_id)
    timings = {timing['day_of_week']: timing for timing in timings_list}
    days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    timings_text = ""
    for i, day in enumerate(days_of_week):
        timing = timings.get(i)
        if timing:
            timings_text += f"\n- **{day}**: {timing['start_time'].strftime('%H:%M')} - {timing['end_time'].strftime('%H:%M')}"

    if not timings_text:
        timings_text = "\n- Тайминги еще не настроены."

    await state.set_state(CampaignStates.timing_select_days)
    await state.update_data(campaign_id=campaign_id, selected_days=[])

    options = [(day, str(i)) for i, day in enumerate(days_of_week)]
    data = await state.get_data()
    selected_days = data.get('selected_days', [])

    keyboard = get_multiselect_keyboard(
        options=options,
        selected_values=selected_days,
        done_callback=f"timing_days_done:{campaign_id}",
        back_callback=f"campaign_view:{campaign_id}"
    )

    message_text = (
        f"**🗓️ Настройка Времени Постинга для '{campaign_name}'**\n"
        f"\n**Текущие настройки:**{timings_text}\n\n"
        "Выберите дни, для которых вы хотите установить или изменить время. "
        "Нажмите 'Готово', когда закончите выбор."
    )

    if isinstance(query_or_message, CallbackQuery):
        await message.edit_text(message_text, reply_markup=keyboard)
        await query_or_message.answer()
    else:
        await message.answer(message_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("select_toggle:"), CampaignStates.timing_select_days)
async def toggle_day_selection(callback: CallbackQuery, state: FSMContext):
    """Toggles the selection of a day in the timing multi-select."""
    day_index_to_toggle = callback.data.split(":")[1]

    data = await state.get_data()
    selected_days = data.get('selected_days', [])

    if day_index_to_toggle in selected_days:
        selected_days.remove(day_index_to_toggle)
    else:
        selected_days.append(day_index_to_toggle)

    await state.update_data(selected_days=selected_days)

    campaign_id = data['campaign_id']
    days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    options = [(day, str(i)) for i, day in enumerate(days_of_week)]

    keyboard = get_multiselect_keyboard(
        options=options,
        selected_values=selected_days,
        done_callback=f"timing_days_done:{campaign_id}",
        back_callback=f"campaign_view:{campaign_id}"
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "select_all_toggle", CampaignStates.timing_select_days)
async def toggle_select_all_days(callback: CallbackQuery, state: FSMContext):
    """Toggles the selection of all days."""
    data = await state.get_data()
    selected_days = data.get('selected_days', [])
    days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    all_day_indices = [str(i) for i in range(len(days_of_week))]

    if len(selected_days) == len(all_day_indices):
        new_selected_days = []
    else:
        new_selected_days = all_day_indices

    await state.update_data(selected_days=new_selected_days)

    campaign_id = data['campaign_id']
    options = [(day, str(i)) for i, day in enumerate(days_of_week)]

    keyboard = get_multiselect_keyboard(
        options=options,
        selected_values=new_selected_days,
        done_callback=f"timing_days_done:{campaign_id}",
        back_callback=f"campaign_view:{campaign_id}"
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("timing_days_done:"), CampaignStates.timing_select_days)
async def timing_days_done(callback: CallbackQuery, state: FSMContext):
    """Handles completion of day selection and asks for start time."""
    data = await state.get_data()
    selected_days = data.get('selected_days', [])

    if not selected_days:
        await callback.answer("⚠️ Пожалуйста, выберите хотя бы один день.", show_alert=True)
        return

    await state.set_state(CampaignStates.timing_input_start)
    
    days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    selected_day_names = [days_of_week[int(i)] for i in selected_days]

    await callback.message.edit_text(
        f"**🕒 Выбраны дни:** {', '.join(selected_day_names)}\n\n"
        "Теперь введите **время начала** для этих дней.\n"
        "Формат: **HH:MM** (например, 09:00)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"campaign_edit_timings:{data['campaign_id']}")]
        ])
    )
    await callback.answer()


@router.message(CampaignStates.timing_input_start, F.text)
async def timing_input_start(message: Message, state: FSMContext):
    """Inputs start time for selected days."""
    start_time_str = message.text.strip()
    try:
        # Validate format, but don't store the object
        datetime.strptime(start_time_str, "%H:%M").time()
        await state.update_data(start_time=start_time_str)  # Store the string
        await state.set_state(CampaignStates.timing_input_end)
        await message.answer(f"✅ Время начала: **{start_time_str}**. Теперь введите **время окончания** (HH:MM):")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате **HH:MM** (например, 09:00):")


@router.message(CampaignStates.timing_input_end, F.text)
async def timing_input_end(message: Message, state: FSMContext):
    """Inputs end time and saves timing for all selected days."""
    data = await state.get_data()
    campaign_mgr = get_campaign_manager()
    campaign_id = data['campaign_id']
    selected_days_indices = data.get('selected_days', [])

    end_time_str = message.text.strip()
    try:
        end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()
        # Retrieve the string and convert it to a time object now
        start_time_str = data['start_time']
        start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()

        if end_time_obj <= start_time_obj:
            await message.answer("❌ Время окончания должно быть позже времени начала. Попробуйте снова:")
            return

        # Save timing for each selected day
        for day_index_str in selected_days_indices:
            await campaign_mgr.save_timing(
                campaign_id=campaign_id,
                day=int(day_index_str),
                start_time=start_time_obj,
                end_time=end_time_obj
            )
        
        days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        selected_day_names = [days_of_week[int(i)] for i in selected_days_indices]

        await message.answer(
            f"✅ Тайминги для **{', '.join(selected_day_names)}** сохранены: **{start_time_obj.strftime('%H:%M')} - {end_time_obj.strftime('%H:%M')}**."
        )

        await state.clear()
        await edit_campaign_timings(message, state, campaign_id)

    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате **HH:MM** (например, 23:30):")
    except Exception as e:
        bot_logger.log_error("Manage Module", e, f"Ошибка при сохранении времени окончания для кампании {campaign_id}")
        await message.answer("Произошла ошибка при сохранении. Попробуйте позже.")
        await state.clear()

# REMOVED: Old timing handlers: start_timing_setup, timing_select_day, timing_input_start, timing_input_end

# --- IMPROVED DELETE WORKFLOW ---

@router.callback_query(F.data.startswith("campaign_delete_confirm:"))
async def confirm_delete_campaign(callback: CallbackQuery, state: FSMContext):
    """Asks for final confirmation before deleting a campaign."""
    campaign_id = int(callback.data.split(":")[1])

    # 1. Получаем имя для подтверждения
    campaign_mgr = get_campaign_manager()
    campaign = await campaign_mgr.get_campaign_details(campaign_id) if campaign_mgr else None
    if not campaign:
        await callback.answer("❌ Кампания не найдена.", show_alert=True)
        return

    await state.set_state(CampaignStates.delete_confirmation)
    await state.update_data(campaign_id=campaign_id)

    await callback.message.edit_text(
        f"⚠️ **ВНИМАНИЕ!** Вы уверены, что хотите удалить кампанию **'{campaign['name']}'** и все ее тайминги?\n"
        "Это действие необратимо!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить окончательно", callback_data=f"campaign_delete_finalize:{campaign_id}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"campaign_edit:{campaign_id}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign_delete_finalize:"), CampaignStates.delete_confirmation)
async def finalize_delete_campaign(callback: CallbackQuery, state: FSMContext):
    """Deletes the campaign after checking the state."""
    campaign_id = int(callback.data.split(":")[1])

    # 1. Получаем имя для логирования
    campaign_mgr = get_campaign_manager()
    campaign = await campaign_mgr.get_campaign_details(campaign_id) if campaign_mgr else None
    campaign_name = campaign['name'] if campaign else f"ID {campaign_id}"

    try:
        if campaign_mgr:
            await campaign_mgr.delete_campaign(campaign_id)

        # Логирование
        bot_logger.log_campaign_change(
            campaign_id,
            f"Удалена кампания '{campaign_name}'",
            callback.from_user.id
        )

        await callback.message.edit_text(f"🗑 Кампания **'{campaign_name}'** успешно удалена.")

        # Возврат в главное меню кампаний
        from handlers.campaigns.manage import enter_campaign_module
        await enter_campaign_module(callback, state)

    except Exception as e:
        bot_logger.log_error("Manage Module", e, f"Ошибка при удалении кампании {campaign_id}")
        await callback.message.edit_text(f"❌ Произошла ошибка при удалении: {e}")

    await callback.answer()
