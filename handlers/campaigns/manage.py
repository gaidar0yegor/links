# handlers/campaigns/manage.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.campaign_states import CampaignStates
from services.campaign_manager import get_campaign_manager

from datetime import datetime

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
        [InlineKeyboardButton(text="⏰ Установить/Изменить тайминги (2.4)", callback_data=f"campaign_timing:start:{campaign_id}")],
        [InlineKeyboardButton(text="🗑 Удалить кампанию", callback_data=f"campaign_delete:{campaign_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_campaign_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS_MAPPING = {i: day for i, day in enumerate(DAYS)} # 0: "Пн", 1: "Вт" и т.д.

def get_day_select_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора дня недели."""
    buttons = []
    # Кнопки для каждого дня недели
    for i, day in DAYS_MAPPING.items():
        buttons.append([InlineKeyboardButton(text=day, callback_data=f"timing_day:{i}:{campaign_id}")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад к управлению", callback_data=f"campaign_edit:{campaign_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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

@router.callback_query(F.data.startswith("campaign_timing:start:"))
async def start_timing_setup(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс установки таймингов."""
    # Получаем ID из колбэка
    campaign_id = int(callback.data.split(":")[2])

    # Переходим в FSM для таймингов
    await state.set_state(CampaignStates.campaign_timing_select_day)
    # Сохраняем ID, если он не сохранен (на случай прямого перехода)
    await state.update_data({'current_campaign_id': campaign_id})

    # Получаем текущие тайминги для отображения
    campaign_mgr = get_campaign_manager()
    current_timings = await campaign_mgr.get_timings(campaign_id) if campaign_mgr else []
    timings_text = "Текущие тайминги:\n"
    if current_timings:
        for t in current_timings:
            day_name = DAYS_MAPPING.get(t['day_of_week'], 'Н/Д')
            timings_text += f" - {day_name}: с {t['start_time']} до {t['end_time']}\n"
    else:
        timings_text += "Тайминги не заданы.\n"

    await callback.message.edit_text(
        f"**Установка таймингов (2.4)**\n\n{timings_text}\n\n"
        "Выберите **день недели** для добавления или изменения интервала:",
        reply_markup=get_day_select_keyboard(campaign_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("timing_day:"), CampaignStates.campaign_timing_select_day)
async def timing_select_day(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор дня недели и просит ввести время начала."""
    _, day_index_str, campaign_id_str = callback.data.split(":")
    day_index = int(day_index_str)
    day_name = DAYS_MAPPING[day_index]

    # Сохраняем выбранный день и переходим к вводу времени начала
    await state.update_data(timing_setup={'day_index': day_index, 'day_name': day_name})
    await state.set_state(CampaignStates.campaign_timing_input_start)

    await callback.message.edit_text(
        f"Выбран день: **{day_name}**.\n\n"
        "Введите **время начала** постинга в формате ЧЧ:ММ (например, 10:30):"
    )
    await callback.answer()

@router.message(CampaignStates.campaign_timing_input_start, F.text)
async def timing_input_start(message: Message, state: FSMContext):
    """Обрабатывает ввод времени начала и просит ввести время окончания."""
    start_time_str = message.text.strip()

    try:
        # Проверяем формат времени
        start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
    except ValueError:
        await message.answer("⚠️ Неверный формат времени. Введите в формате ЧЧ:ММ (например, 10:30).")
        return

    data = await state.get_data()
    timing_setup = data['timing_setup']
    timing_setup['start_time'] = start_time_str

    await state.update_data(timing_setup=timing_setup)
    await state.set_state(CampaignStates.campaign_timing_input_end)

    await message.answer(
        f"Время начала: **{start_time_str}**.\n\n"
        "Введите **время окончания** постинга в формате ЧЧ:ММ (например, 18:00):"
    )

@router.message(CampaignStates.campaign_timing_input_end, F.text)
async def timing_input_end(message: Message, state: FSMContext):
    """Обрабатывает ввод времени окончания и сохраняет тайминг."""
    end_time_str = message.text.strip()

    try:
        # Проверяем формат времени
        end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()
    except ValueError:
        await message.answer("⚠️ Неверный формат времени. Введите в формате ЧЧ:ММ (например, 18:00).")
        return

    data = await state.get_data()
    timing_setup = data['timing_setup']
    campaign_id = data['current_campaign_id']

    # Проверка, что время начала раньше времени окончания
    start_time_obj = datetime.strptime(timing_setup['start_time'], "%H:%M").time()
    if end_time_obj <= start_time_obj:
        await message.answer("⚠️ Время окончания должно быть позже времени начала.")
        return

    # Сохранение тайминга (2.4)
    campaign_mgr = get_campaign_manager()
    if campaign_mgr:
        await campaign_mgr.save_timing(
            campaign_id=campaign_id,
            day=timing_setup['day_index'],
            start_time=timing_setup['start_time'],
            end_time=end_time_str
        )

    await message.answer(
        f"✅ Тайминг для **{timing_setup['day_name']}** успешно установлен: с {timing_setup['start_time']} до {end_time_str}."
    )

    # Сброс FSM для таймингов и возврат в меню выбора дня
    await state.set_state(CampaignStates.campaign_timing_select_day)

    # Переоткрываем меню выбора дня, чтобы показать обновленные тайминги
    # Имитируем нажатие кнопки 'campaign_timing:start'
    temp_callback_data = f"campaign_timing:start:{campaign_id}"
    await start_timing_setup(message, state) # Перезапуск отображения

@router.callback_query(F.data.startswith("campaign_delete:"))
async def confirm_delete_campaign(callback: CallbackQuery):
    """Запрашивает подтверждение перед удалением."""
    campaign_id = int(callback.data.split(":")[1])

    # 1. Получаем имя для подтверждения
    campaign_mgr = get_campaign_manager()
    campaign = await campaign_mgr.get_campaign_details(campaign_id) if campaign_mgr else None
    if not campaign:
        await callback.answer("❌ Кампания не найдена.", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚠️ **ВНИМАНИЕ!** Вы уверены, что хотите удалить кампанию **'{campaign['name']}'** и все ее тайминги?\n"
        "Это действие необратимо!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить окончательно", callback_data=f"campaign_final_delete:{campaign_id}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"campaign_edit:{campaign_id}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign_final_delete:"))
async def finalize_delete_campaign(callback: CallbackQuery, state: FSMContext):
    """Выполняет удаление кампании."""
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
