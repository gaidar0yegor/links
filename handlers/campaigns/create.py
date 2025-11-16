# handlers/campaigns/create.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from typing import List, Tuple
from states.campaign_states import CampaignStates
from services.sheets_api import sheets_api
from services.campaign_manager import campaign_manager
from handlers.campaigns.keyboards import get_multiselect_keyboard
from handlers.main_menu import MainMenuCallback # Для кнопки "Назад"

router = Router()
# --- Вспомогательные функции ---

# Эта функция будет вызываться, чтобы получить данные для мультивыбора из GS
async def get_options_from_gsheets(sheet_name: str) -> List[Tuple[str, str]]:
    """Получает данные (Название, Значение/Callback) для кнопок."""
    data = sheets_api.get_sheet_data(sheet_name)
    # Предполагаем, что первая колонка - Название, вторая - Значение (если нужно)
    # Для каналов: [('Channel A', 'channel_a_id'), ('Channel B', 'channel_b_id')]
    if len(data) > 1 and len(data[0]) >= 2:
        # Пропускаем заголовок
        return [(row[0], row[1]) for row in data[1:] if row[0] and row[1]]
    # Если данные только в одной колонке, используем название как значение
    elif len(data) > 1 and len(data[0]) >= 1:
        return [(row[0], row[0]) for row in data[1:] if row[0]]

    # Fallback options when no Google Sheets data is available
    if sheet_name == "channels":
        return [
            ("@CheapAmazon3332234", "@CheapAmazon3332234"),
            ("Add Custom Channel", "custom_channel")
        ]
    elif sheet_name == "product_categories":
        # Combined categories and subcategories with browse_node_id
        return [
            ("Electronics", "electronics"),
            ("Home & Kitchen", "home"),
            ("Fashion", "fashion"),
            ("Sports", "sports"),
            ("Books", "books"),
            ("Smartphones", "smartphones"),
            ("Laptops", "laptops"),
            ("Headphones", "headphones"),
            ("Cameras", "cameras"),
            ("Gaming", "gaming")
        ]
    elif sheet_name == "languages":
        return [
            ("English", "en"),
            ("Italian", "it"),
            ("Spanish", "es"),
            ("French", "fr")
        ]

    return []

async def get_browse_node_id(category: str, subcategory: str = None) -> str:
    """Get browse_node_id for category/subcategory combination."""
    try:
        data = sheets_api.get_sheet_data("product_categories")
        if len(data) > 1:
            headers = data[0]
            # Expected columns: Category, Subcategory, browse_node_id, active
            col_indices = {header: idx for idx, header in enumerate(headers)}

            for row in data[1:]:
                if len(row) >= len(headers):
                    row_category = row[col_indices.get('Category', 0)].strip()
                    row_subcategory = row[col_indices.get('Subcategory', 1)].strip() if col_indices.get('Subcategory', -1) >= 0 else ""
                    browse_node = row[col_indices.get('browse_node_id', 2)].strip() if col_indices.get('browse_node_id', -1) >= 0 else ""

                    # Match category and subcategory (if provided)
                    if row_category.lower() == category.lower():
                        if not subcategory or row_subcategory.lower() == subcategory.lower():
                            return browse_node
    except Exception as e:
        print(f"Error getting browse_node_id: {e}")

    # Fallback browse node IDs for common categories
    fallback_nodes = {
        "electronics": "1626160311",  # Italy Electronics
        "home": "524015031",  # Italy Home & Kitchen
        "fashion": "1736683031",  # Italy Clothing
        "sports": "524013031",  # Italy Sports
        "books": "411663031",  # Italy Books
        "smartphones": "425916031",  # Italy Smartphones
        "laptops": "425916031",  # Italy Computers
        "headphones": "425916031",  # Italy Audio
        "cameras": "425916031",  # Italy Photo
        "gaming": "425916031"  # Italy Gaming
    }

    return fallback_nodes.get(category.lower(), "1626160311")  # Default to Electronics

# --- Шаг 1: Выбор Канала (2.3.2.1) ---

@router.callback_query(F.data == "campaign_new_start")
async def start_new_campaign(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс создания новой кампании - Шаг 1: Выбор Канала."""
    print(f"🔥 DEBUG: CAMPAIGN CREATE HANDLER CALLED: {callback.data}")
    print(f"🔥 DEBUG: start_new_campaign called with data: {callback.data}")

    await state.set_state(CampaignStates.campaign_new_select_channel)
    # Инициализируем данные кампании в FSM
    await state.update_data(new_campaign={
        'channels': [],
        'categories': [],
        # ... (остальные параметры)
    })

    # 1. Загрузка опций
    options = await get_options_from_gsheets("channels")
    print(f"🔥 DEBUG: Loaded {len(options)} channel options")

    await callback.message.edit_text(
        "**🎯 ШАГ 1: Affiliate Channels** (Мультивыбор)\n\n"
        "💰 Выберите Telegram каналы для автоматического постинга партнерских ссылок Amazon:",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=[], # Пока ничего не выбрано
            done_callback="campaign_done_channels",
            back_callback="back_to_campaign_menu"
        )
    )
    await callback.answer()

# --- Шаг 2: Выбор Категории (2.3.2.2) ---

@router.callback_query(F.data == "campaign_done_channels", CampaignStates.campaign_new_select_channel)
async def done_select_channels(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора каналов и переходит к Шагу 2: Категории."""
    data = await state.get_data()
    selected_channels = data['new_campaign']['channels']

    if not selected_channels:
        await callback.answer("⚠️ Необходимо выбрать хотя бы один канал!", show_alert=True)
        return

    await state.set_state(CampaignStates.campaign_new_select_category)

    # 1. Загрузка опций из объединенной таблицы product_categories
    options = await get_options_from_gsheets("product_categories")

    await callback.message.edit_text(
        "**🎯 ШАГ 2: Product Categories** (Мультивыбор)\n\n"
        "📦 Выберите категории и подкатегории товаров для поиска на Amazon:",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=[], # Пока ничего не выбрано
            done_callback="campaign_done_categories",
            back_callback="campaign_new_start" # Вернуться к выбору каналов
        )
    )
    await callback.answer()

# --- Шаг 3: Выбор Подкатегорий (2.3.2.3) ---

# TODO: Для упрощения, пока игнорируем зависимость от выбранных категорий
@router.callback_query(F.data == "campaign_done_categories", CampaignStates.campaign_new_select_category)
async def done_select_categories(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора категорий и переходит к Шагу 3: Подкатегории."""
    data = await state.get_data()
    selected_categories = data['new_campaign']['categories']

    if not selected_categories:
        await callback.answer("⚠️ Необходимо выбрать хотя бы одну категорию!", show_alert=True)
        return

    await state.set_state(CampaignStates.campaign_new_select_subcategory)

    # 1. Загрузка опций (Из таблицы subcategories)
    # TODO: Реализовать динамическую загрузку, но пока просто загружаем все
    options = await get_options_from_gsheets("subcategories")

    await callback.message.edit_text(
        "**ШАГ 3/N: Выбор подкатегорий** (Мультивыбор)\n\nВыберите подкатегории товаров (опция 'Выбрать все' доступна):",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=[], # Пока ничего не выбрано
            done_callback="campaign_done_subcategories",
            back_callback="campaign_done_channels" # Вернуться к выбору категорий
        )
    )
    await callback.answer()

# --- Шаг 4: Выбор Рейтинга (2.3.2.4) ---

@router.callback_query(F.data == "campaign_done_subcategories", CampaignStates.campaign_new_select_subcategory)
async def done_select_subcategories(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора подкатегорий и переходит к Шагу 4: Рейтинг."""
    data = await state.get_data()
    selected_subcategories = data['new_campaign']['subcategories']

    # Если нет подкатегорий, это не критично, но лучше предупредить
    if not selected_subcategories:
        await callback.answer("⚠️ Подкатегории не выбраны. Кампания будет работать без фильтрации по подкатегориям.", show_alert=True)
        # return # Продолжаем, так как это не обязательное поле по ТЗ

    await state.set_state(CampaignStates.campaign_new_select_rating)

    # Опции рейтинга
    rating_options = [
        ("4.0+ звёзд", "4.0"), # Значение - минимальный рейтинг
        ("4.5+ звёзд", "4.5"),
        ("5.0 звёзд", "5.0")
    ]

    await callback.message.edit_text(
        "**ШАГ 4/N: Выбор рейтинга** (Мультивыбор, минимальный)\n\nВыберите минимальный рейтинг товара:",
        reply_markup=get_multiselect_keyboard(
            options=rating_options,
            selected_values=[],
            done_callback="campaign_done_rating",
            back_callback="campaign_done_categories" # Назад к выбору подкатегорий
        )
    )
    await callback.answer()

# --- Шаг 5: Выбор Языка (2.3.2.5) ---

@router.callback_query(F.data == "campaign_done_rating", CampaignStates.campaign_new_select_rating)
async def done_select_rating(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора рейтинга и переходит к Шагу 5: Язык."""
    data = await state.get_data()
    selected_ratings = data['new_campaign']['ratings'] # Будет сохранено общим хэндлером

    if not selected_ratings:
        await callback.answer("⚠️ Выберите хотя бы один минимальный рейтинг.", show_alert=True)
        return

    # Нормализуем данные: выбираем максимальный рейтинг как единый параметр
    max_rating = max(selected_ratings)

    new_campaign = data['new_campaign']
    new_campaign['rating'] = max_rating

    await state.update_data(new_campaign=new_campaign)
    await state.set_state(CampaignStates.campaign_new_select_language)

    # Опции языка (предполагаем, что они в Google Sheets или заданы жестко)
    language_options = await get_options_from_gsheets("languages") # languages - новая таблица

    await callback.message.edit_text(
        f"**ШАГ 5/N: Выбор языка объявлений**\n\nТекущий минимальный рейтинг: **{max_rating}**\n\nВыберите язык:",
        reply_markup=get_multiselect_keyboard(
            options=language_options,
            selected_values=[], # Тут можно было бы использовать SingleSelect, но используем Multiselect для унификации
            done_callback="campaign_done_language",
            back_callback="campaign_done_subcategories" # Назад к выбору рейтинга
        )
    )
    await callback.answer()

# --- Шаг 6: Ввод Названия (2.3.2.6) ---

@router.callback_query(F.data == "campaign_done_language", CampaignStates.campaign_new_select_language)
async def done_select_language(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора языка и переходит к Шагу 6: Название."""
    data = await state.get_data()
    selected_languages = data['new_campaign']['languages'] # Будет сохранено общим хэндлером

    if not selected_languages:
        await callback.answer("⚠️ Необходимо выбрать язык.", show_alert=True)
        return

    # Если мультивыбор был использован для языка, берем первый выбранный (основной)
    language = selected_languages[0]

    new_campaign = data['new_campaign']
    new_campaign['language'] = language

    await state.update_data(new_campaign=new_campaign)
    await state.set_state(CampaignStates.campaign_new_input_name)

    await callback.message.edit_text(
        "**ШАГ 6/N: Ввод названия кампании**\n\nПожалуйста, введите уникальное название для новой кампании (текстовым сообщением):"
    )
    await callback.answer()

@router.message(CampaignStates.campaign_new_input_name, F.text)
async def input_campaign_name(message: Message, state: FSMContext):
    """Обрабатывает ввод названия кампании и переходит к сохранению."""
    campaign_name = message.text.strip()

    if not campaign_name:
        await message.answer("⚠️ Название кампании не может быть пустым. Попробуйте снова.")
        return

    # 1. Проверка на уникальность (требование 2.3.2.6)
    # TODO: Реализовать асинхронную проверку в CampaignManager
    # is_unique = await campaign_manager.is_name_unique(campaign_name)
    # if not is_unique:
    #     await message.answer(f"⚠️ Кампания с названием '{campaign_name}' уже существует. Введите другое название.")
    #     return

    data = await state.get_data()
    new_campaign = data['new_campaign']
    new_campaign['name'] = campaign_name

    await state.update_data(new_campaign=new_campaign)

    # Переход к финальному шагу: Сохранение / Обзор (2.3.2.7)
    await state.set_state(CampaignStates.campaign_new_review)

    # Выводим обзор параметров перед сохранением
    summary = f"""
    ✅ **Параметры кампании собраны:**

    - **Название:** {campaign_name}
    - **Каналы:** {', '.join(new_campaign.get('channels', []))}
    - **Категории:** {', '.join(new_campaign.get('categories', []))}
    - **Подкатегории:** {len(new_campaign.get('subcategories', []))} выбрано
    - **Мин. Рейтинг:** {new_campaign.get('rating', 'Не выбран')}
    - **Язык:** {new_campaign.get('language', 'Не выбран')}

    Вы готовы **СОХРАНИТЬ** кампанию?
    """

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить и выйти", callback_data="campaign_final_save")],
        [InlineKeyboardButton(text="⬅️ Назад (Изменить название)", callback_data="campaign_done_language")] # Вернуться на Шаг 5
    ])

    await message.answer(summary, reply_markup=keyboard)


# --- Общий Хэндлер для Обработки Мультивыбора ---

@router.callback_query(F.data.startswith("select_toggle:"))
async def toggle_selection(callback: CallbackQuery, state: FSMContext):
    """Переключает выбор элемента в текущем мультивыборе."""
    # Получаем значение, которое нужно переключить
    value_to_toggle = callback.data.split(":")[1]

    data = await state.get_data()
    new_campaign = data.get('new_campaign', {})

    # Определяем, какой ключ в 'new_campaign' мы сейчас редактируем,
    # исходя из текущего состояния FSM
    current_state = await state.get_state()

    if current_state == CampaignStates.campaign_new_select_channel:
        key = 'channels'
        options_sheet = 'channels'
    elif current_state == CampaignStates.campaign_new_select_category:
        key = 'categories'
        options_sheet = 'categories'
    elif current_state == CampaignStates.campaign_new_select_subcategory:
        key = 'subcategories'
        options_sheet = 'subcategories'
    elif current_state == CampaignStates.campaign_new_select_rating:
        key = 'ratings'
        options_sheet = 'ratings'  # This would be a hardcoded list, but we'll handle it differently
    elif current_state == CampaignStates.campaign_new_select_language:
        key = 'languages'
        options_sheet = 'languages'
    else:
        await callback.answer("Ошибка состояния.", show_alert=True)
        return

    selected_list = new_campaign.get(key, [])

    if value_to_toggle in selected_list:
        selected_list.remove(value_to_toggle)
    else:
        selected_list.append(value_to_toggle)

    new_campaign[key] = selected_list
    await state.update_data(new_campaign=new_campaign)

    # Перерисовываем клавиатуру с обновленным выбором
    if key == 'ratings':
        # Hardcoded options for rating
        options = [
            ("4.0+ звёзд", "4.0"),
            ("4.5+ звёзд", "4.5"),
            ("5.0 звёзд", "5.0")
        ]
        done_callback = "campaign_done_rating"
        back_callback = "campaign_done_subcategories"
    elif key == 'languages':
        options = await get_options_from_gsheets(options_sheet)
        done_callback = "campaign_done_language"
        back_callback = "campaign_done_subcategories"
    else:
        options = await get_options_from_gsheets(options_sheet)
        # Определяем нужный done_callback (для каждой кнопки он свой)
        if key == 'channels': done_callback = "campaign_done_channels"
        elif key == 'categories': done_callback = "campaign_done_categories"
        elif key == 'subcategories': done_callback = "campaign_done_subcategories"

        # Определяем нужный back_callback
        if key == 'channels': back_callback = "back_to_campaign_menu"
        elif key == 'categories': back_callback = "campaign_done_channels"
        elif key == 'subcategories': back_callback = "campaign_done_categories"

    await callback.message.edit_reply_markup(
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=selected_list,
            done_callback=done_callback,
            back_callback=back_callback
        )
    )
    await callback.answer()

@router.callback_query(F.data == "select_all_toggle")
async def toggle_select_all(callback: CallbackQuery, state: FSMContext):
    """Переключает выбор всех элементов."""
    data = await state.get_data()
    new_campaign = data.get('new_campaign', {})

    current_state = await state.get_state()

    if current_state == CampaignStates.campaign_new_select_channel:
        key = 'channels'
        options_sheet = 'channels'
        done_callback = "campaign_done_channels"
        back_callback = "back_to_campaign_menu"
    elif current_state == CampaignStates.campaign_new_select_category:
        key = 'categories'
        options_sheet = 'categories'
        done_callback = "campaign_done_categories"
        back_callback = "campaign_done_channels"
    elif current_state == CampaignStates.campaign_new_select_subcategory:
        key = 'subcategories'
        options_sheet = 'subcategories'
        done_callback = "campaign_done_subcategories"
        back_callback = "campaign_done_categories"
    elif current_state == CampaignStates.campaign_new_select_rating:
        key = 'ratings'
        # Hardcoded options for rating
        options = [
            ("4.0+ звёзд", "4.0"),
            ("4.5+ звёзд", "4.5"),
            ("5.0 звёзд", "5.0")
        ]
        done_callback = "campaign_done_rating"
        back_callback = "campaign_done_subcategories"
    elif current_state == CampaignStates.campaign_new_select_language:
        key = 'languages'
        options_sheet = 'languages'
        done_callback = "campaign_done_language"
        back_callback = "campaign_done_subcategories"
    else:
        await callback.answer("Ошибка состояния.", show_alert=True)
        return

    if key == 'ratings':
        # Already have options defined above
        all_values = [val for name, val in options]
    else:
        options = await get_options_from_gsheets(options_sheet)
        all_values = [val for name, val in options]

    selected_list = new_campaign.get(key, [])

    if len(selected_list) == len(all_values):
        # Если все выбраны, то сбрасываем выбор
        new_campaign[key] = []
    else:
        # Иначе выбираем все
        new_campaign[key] = all_values

    await state.update_data(new_campaign=new_campaign)

    await callback.message.edit_reply_markup(
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=new_campaign[key],
            done_callback=done_callback,
            back_callback=back_callback
        )
    )
    await callback.answer()

# --- Финальный Хэндлер Сохранения ---

@router.callback_query(F.data == "campaign_final_save", CampaignStates.campaign_new_review)
async def finalize_and_save_campaign(callback: CallbackQuery, state: FSMContext):
    """Финальное сохранение кампании в базу данных."""
    data = await state.get_data()
    campaign_data = data['new_campaign']

    try:
        # Add browse_node_id for each selected category
        categories_with_nodes = []
        for category in campaign_data.get('categories', []):
            browse_node = await get_browse_node_id(category)
            categories_with_nodes.append({
                'name': category,
                'browse_node_id': browse_node
            })

        campaign_data['categories_with_nodes'] = categories_with_nodes

        # Проверка уникальности
        is_unique = await campaign_manager.is_name_unique(campaign_data['name'])
        if not is_unique:
            await callback.answer(f"⚠️ Кампания с названием '{campaign_data['name']}' уже существует. Измените название.", show_alert=True)
            # Возвращаемся на шаг ввода названия
            await state.set_state(CampaignStates.campaign_new_input_name)
            await callback.message.edit_text("Пожалуйста, введите другое, уникальное название для новой кампании:")
            return

        campaign_id = await campaign_manager.save_new_campaign(campaign_data)

        await callback.message.edit_text(
            f"🎉 Кампания **'{campaign_data['name']}'** успешно создана с ID: {campaign_id}.\n"
            f"Текущий статус: **Не выбраны тайминги**.\n\n"
            "Вы можете продолжить работу в Главном меню."
        )

        # Сброс FSM и переход в меню кампаний
        await state.clear()
        # Возвращаемся в меню кампаний, чтобы увидеть новую кампанию
        await enter_campaign_module(callback)

    except Exception as e:
        await callback.message.edit_text(f"❌ Критическая ошибка при сохранении кампании: {e}")
        await state.clear()

    await callback.answer()

# Хэндлер для кнопки "назад" в меню кампаний
from handlers.campaigns.manage import enter_campaign_module
router.callback_query(F.data == "back_to_campaign_menu")(enter_campaign_module)
