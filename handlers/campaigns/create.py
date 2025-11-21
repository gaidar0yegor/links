# handlers/campaigns/create.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from typing import List, Tuple
from states.campaign_states import CampaignStates
from services.sheets_api import sheets_api
from services.campaign_manager import get_campaign_manager
from handlers.campaigns.keyboards import get_multiselect_keyboard


router = Router()
# --- Вспомогательные функции ---

# Эта функция будет вызываться, чтобы получить данные для мультивыбора из GS
async def get_options_from_gsheets(sheet_name: str) -> List[Tuple[str, str]]:
    """Получает данные (Название, Значение/Callback) для кнопок."""
    if sheet_name == "categories":
        # Use new unified categories_subcategories table
        categories = sheets_api.get_unique_categories()
        # Возвращаем имя категории как значение для callback_data
        return [(cat["name"], cat["name"]) for cat in categories]
    elif sheet_name == "subcategories":
        # This will be handled dynamically based on selected categories
        return []

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
            ("Russian", "ru")
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
    # Инициализируем данные кампании в FSM, добавляем ID создателя
    await state.update_data(new_campaign={
        'created_by_user_id': callback.from_user.id,
        'channels': [],
        'categories': [],
        # ... (остальные параметры)
    })

    # 1. Загрузка опций
    options = await get_options_from_gsheets("channels")
    print(f"🔥 DEBUG: Loaded {len(options)} channel options")

    await callback.message.edit_text(
        "<b>🎯 ШАГ 1: Affiliate Channels</b> (Мультивыбор)\n\n"
        "💰 Выберите Telegram каналы для автоматического постинга партнерских ссылок Amazon:",
        parse_mode="HTML",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=[], # Пока ничего не выбрано
            done_callback="campaign_done_channels",
            back_callback="back_to_campaign_menu"
        )
    )
    await callback.answer()

# --- Шаг 2: Выбор Категорий (2.3.2.2) ---

@router.callback_query(F.data == "campaign_done_channels", CampaignStates.campaign_new_select_channel)
async def done_select_channels(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора каналов и переходит к Шагу 2: Категории."""
    data = await state.get_data()
    selected_channels = data['new_campaign']['channels']

    if not selected_channels:
        await callback.answer("⚠️ Необходимо выбрать хотя бы один канал!", show_alert=True)
        return

    await state.set_state(CampaignStates.campaign_new_select_category)

    # Load categories from new unified table
    options = await get_options_from_gsheets("categories")
    print(f"🔥 DEBUG: Loaded {len(options)} category options for Step 2")

    await callback.message.edit_text(
        "<b>🎯 ШАГ 2: Product Categories</b> (Мультивыбор)\n\n"
        "📦 Выберите категории товаров для поиска на Amazon.\n"
        "После выбора категорий вы сможете выбрать подкатегории для каждой:",
        parse_mode="HTML",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=[], # Пока ничего не выбрано
            done_callback="campaign_done_categories",
            back_callback="campaign_new_start" # Вернуться к выбору каналов
        )
    )
    await callback.answer()

# --- Шаг 3: Выбор Подкатегорий по Категориям (2.3.2.3) ---

@router.callback_query(F.data == "campaign_done_categories", CampaignStates.campaign_new_select_category)
async def done_select_categories(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора категорий и начинает выбор подкатегорий."""
    data = await state.get_data()
    selected_categories = data['new_campaign']['categories']

    if not selected_categories:
        await callback.answer("⚠️ Необходимо выбрать хотя бы одну категорию!", show_alert=True)
        return

    # Initialize subcategories selection
    await state.update_data(
        new_campaign={
            **data['new_campaign'],
            'subcategories': {},
            'current_category_index': 0
        }
    )

    # Start with first category
    await show_subcategories_for_category(callback, state)

async def show_subcategories_for_category(callback: CallbackQuery, state: FSMContext):
    """Показывает подкатегории для текущей категории."""
    data = await state.get_data()
    selected_categories = data['new_campaign']['categories']
    current_index = data['new_campaign'].get('current_category_index', 0)
    subcategories_data = data['new_campaign'].get('subcategories', {})

    if current_index >= len(selected_categories):
        # All categories processed, move to next step
        await done_select_all_subcategories(callback, state)
        return

    current_category = selected_categories[current_index]
    subcategories = sheets_api.get_subcategories_for_category(current_category)

    if not subcategories:
        # No subcategories for this category, skip to next
        await state.update_data(
            new_campaign={
                **data['new_campaign'],
                'current_category_index': current_index + 1
            }
        )
        await show_subcategories_for_category(callback, state)
        return

    # Convert to options format with indices to avoid callback data length issues
    options = [(sub['name'], str(idx)) for idx, sub in enumerate(subcategories)]
    selected_indices = []

    # Convert selected subcategory names to indices
    selected_subs = subcategories_data.get(current_category, [])
    for idx, sub in enumerate(subcategories):
        if sub['name'] in selected_subs:
            selected_indices.append(str(idx))

    progress_text = f"<b>Категория {current_index + 1}/{len(selected_categories)}: {current_category}</b>\n\n"
    progress_text += "Выберите подкатегории (или 'Выбрать все' для всей категории):"

    await state.set_state(CampaignStates.campaign_new_select_subcategory)

    await callback.message.edit_text(
        f"<b>🎯 ШАГ 3: Подкатегории</b> (Мультивыбор)\n\n{progress_text}",
        parse_mode="HTML",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=selected_indices,
            done_callback=f"campaign_done_subcategories:{current_index}",
            back_callback="back_to_categories_from_subcategories"
        )
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_categories_from_subcategories", CampaignStates.campaign_new_select_subcategory)
async def back_to_categories_from_subcategories(callback: CallbackQuery, state: FSMContext):
    """Возвращает к выбору категорий из меню подкатегорий."""
    data = await state.get_data()
    selected_categories = data['new_campaign'].get('categories', [])
    
    # Сбрасываем индекс текущей категории
    await state.update_data(
        new_campaign={
            **data['new_campaign'],
            'current_category_index': 0
        }
    )
    
    await state.set_state(CampaignStates.campaign_new_select_category)
    
    # Загружаем категории
    options = await get_options_from_gsheets("categories")
    
    # Получаем уже выбранные категории для отображения
    selected_values = [cat for cat in selected_categories]
    
    await callback.message.edit_text(
        "<b>🎯 ШАГ 2: Product Categories</b> (Мультивыбор)\n\n"
        "📦 Выберите категории товаров для поиска на Amazon.\n"
        "После выбора категорий вы сможете выбрать подкатегории для каждой:",
        parse_mode="HTML",
        reply_markup=get_multiselect_keyboard(
            options=options,
            selected_values=selected_values,
            done_callback="campaign_done_categories",
            back_callback="campaign_new_start"
        )
    )
    await callback.answer()

@router.callback_query(F.data.startswith("campaign_done_subcategories:"), CampaignStates.campaign_new_select_subcategory)
async def done_select_subcategories_for_category(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора подкатегорий для текущей категории."""
    # category_name = callback.data.split(":", 1)[1] # No longer needed

    data = await state.get_data()
    current_index = data['new_campaign'].get('current_category_index', 0)
    # subcategories_data = data['new_campaign'].get('subcategories', {}) # Not needed

    # Get selected subcategories for this category
    # selected_subs = subcategories_data.get(category_name, []) # Not needed

    # Save selection and move to next category
    await state.update_data(
        new_campaign={
            **data['new_campaign'],
            'current_category_index': current_index + 1
        }
    )

    await show_subcategories_for_category(callback, state)

async def done_select_all_subcategories(callback: CallbackQuery, state: FSMContext):
    """Все подкатегории выбраны, переходим к следующему шагу."""
    await state.set_state(CampaignStates.campaign_new_select_rating)

    # Опции рейтинга
    rating_options = [
        ("3.5+ звёзд", "3.5"),
        ("4.0+ звёзд", "4.0"),
        ("4.5+ звёзд", "4.5"),
        ("4.8+ звёзд", "4.8")
    ]

    await callback.message.edit_text(
        "<b>ШАГ 4: Выбор рейтинга</b> (Мультивыбор)\n\n"
        "⭐ Выберите минимальный рейтинг товара:",
        parse_mode="HTML",
        reply_markup=get_multiselect_keyboard(
            options=rating_options,
            selected_values=[],
            done_callback="campaign_done_rating",
            back_callback="campaign_done_categories"
        )
            )
    await callback.answer()

# --- REMOVED: Redundant handler that conflicts with subcategories flow ---
# The subcategories selection now properly flows through done_select_all_subcategories()

# --- Шаг 5: Выбор Языка (2.3.2.5) ---

@router.callback_query(F.data == "campaign_done_rating", CampaignStates.campaign_new_select_rating)
async def done_select_rating(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора рейтинга и переходит к Шагу 5: Мин. цена."""
    data = await state.get_data()
    selected_ratings = data['new_campaign'].get('ratings', [])

    if not selected_ratings:
        await callback.answer("⚠️ Выберите хотя бы один минимальный рейтинг.", show_alert=True)
        return

    max_rating = max(float(r) for r in selected_ratings)
    new_campaign = data['new_campaign']
    new_campaign['rating'] = max_rating
    await state.update_data(new_campaign=new_campaign)

    await state.set_state(CampaignStates.campaign_new_input_min_price)

    await callback.message.edit_text(
        f"<b>ШАГ 5: Минимальная цена</b>\n\n"
        f"Текущий минимальный рейтинг: <b>{max_rating}</b>\n\n"
        "Введите минимальную цену для товаров (например, `25` для €25). "
        "Отправьте `0`, чтобы пропустить.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CampaignStates.campaign_new_input_min_price, F.text)
async def input_min_price(message: Message, state: FSMContext):
    """Обрабатывает ввод мин. цены и переходит к Шагу 6: FBA."""
    try:
        min_price = float(message.text.strip())
        if min_price < 0:
            raise ValueError("Price cannot be negative")

        data = await state.get_data()
        new_campaign = data['new_campaign']
        new_campaign['min_price'] = min_price if min_price > 0 else None
        # Удаляем параметр скидки, если он был
        new_campaign.pop('min_saving_percent', None)
        await state.update_data(new_campaign=new_campaign)

        await state.set_state(CampaignStates.campaign_new_select_fba)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="fba:yes")],
            [InlineKeyboardButton(text="Нет", callback_data="fba:no")],
            [InlineKeyboardButton(text="Неважно", callback_data="fba:skip")]
        ])
        await message.answer(
            "<b>ШАГ 6: Fulfilled By Amazon (FBA)</b>\n\n"
            "Искать только товары, доставляемые Amazon?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except ValueError:
        await message.answer("❌ Введите корректное число (например, `25` или `0`).")


@router.callback_query(F.data.startswith("fba:"), CampaignStates.campaign_new_select_fba)
async def select_fba(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор FBA и переходит к Шагу 7: Sales Rank Threshold."""
    choice = callback.data.split(":")[1]
    fba_status = {
        'yes': True,
        'no': False,
        'skip': None
    }.get(choice)

    data = await state.get_data()
    new_campaign = data['new_campaign']
    new_campaign['fulfilled_by_amazon'] = fba_status
    await state.update_data(new_campaign=new_campaign)

    await state.set_state(CampaignStates.campaign_new_input_max_sales_rank)

    await callback.message.edit_text(
        "<b>ШАГ 7: Максимальный Sales Rank</b>\n\n"
        "🎯 <b>Упрощенная система качества</b>\n\n"
        "Введите максимальный Sales Rank для товаров (рекомендуется: 10000).\n"
        "Чем меньше число, тем лучше продаются товары.\n\n"
        "Примеры:\n"
        "• `10000` - товары из топ-10000 продаж\n"
        "• `5000` - более качественные товары\n"
        "• `50000` - более широкий выбор\n\n"
        "Отправьте число или `0` для значения по умолчанию (10000):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CampaignStates.campaign_new_input_max_sales_rank, F.text)
async def input_max_sales_rank(message: Message, state: FSMContext):
    """Обрабатывает ввод максимального Sales Rank и переходит к Шагу 8: Язык."""
    try:
        max_rank = int(message.text.strip())
        if max_rank < 0:
            raise ValueError("Sales rank cannot be negative")

        # Use default if 0 is entered
        if max_rank == 0:
            max_rank = 10000

        data = await state.get_data()
        new_campaign = data['new_campaign']
        new_campaign['max_sales_rank'] = max_rank
        await state.update_data(new_campaign=new_campaign)

        await state.set_state(CampaignStates.campaign_new_select_language)

        language_options = await get_options_from_gsheets("languages")
        await message.answer(
            "<b>ШАГ 8: Выбор языка объявлений</b>\n\nВыберите язык:",
            parse_mode="HTML",
            reply_markup=get_multiselect_keyboard(
                options=language_options,
                selected_values=[],
                done_callback="campaign_done_language",
                back_callback="campaign_done_rating"  # Allows going back to rating
            )
        )

    except ValueError:
        await message.answer("❌ Введите корректное число (например, `10000` или `0` для значения по умолчанию).")


@router.callback_query(F.data == "campaign_done_language", CampaignStates.campaign_new_select_language)
async def done_select_language(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает завершение выбора языка и переходит к Шагу 9: Название."""
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
        "<b>ШАГ 9: Ввод названия кампании</b>\n\nПожалуйста, введите уникальное название для новой кампании (текстовым сообщением):",
        parse_mode="HTML"
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
    subcategories_info = []
    subcategories_data = new_campaign.get('subcategories', {})
    for category, subs in subcategories_data.items():
        if subs:
            subcategories_info.append(f"{category}: {', '.join(subs)}")

    summary = f"""
    ✅ <b>Параметры кампании собраны:</b>

    - <b>Название:</b> {campaign_name}
    - <b>Каналы:</b> {', '.join(new_campaign.get('channels', []))}
    - <b>Категории:</b> {', '.join(new_campaign.get('categories', []))}
    - <b>Подкатегории:</b> {len(subcategories_info)} категорий с подкатегориями
    """

    if subcategories_info:
        summary += "      " + "\n      ".join(subcategories_info[:3])  # Show first 3
        if len(subcategories_info) > 3:
            summary += f"\n      ... и ещё {len(subcategories_info) - 3} категорий"

    summary += f"""
    - <b>Мин. Рейтинг:</b> {new_campaign.get('rating', 'Не выбран')}
    - <b>Мин. Цена:</b> €{new_campaign.get('min_price', 'Нет')}
    - <b>FBA:</b> {new_campaign.get('fulfilled_by_amazon', 'Неважно')}
    - <b>Язык:</b> {new_campaign.get('language', 'Не выбран')}

    Вы готовы <b>СОХРАНИТЬ</b> кампанию?
    """

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить и выйти", callback_data="campaign_final_save")],
        [InlineKeyboardButton(text="⬅️ Назад (Изменить название)", callback_data="campaign_done_language")] # Вернуться на Шаг 5
    ])

    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")


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
        # Handle subcategories selection for current category using indices
        current_index = data['new_campaign'].get('current_category_index', 0)
        selected_categories = data['new_campaign']['categories']
        if current_index < len(selected_categories):
            current_category = selected_categories[current_index]
            subcategories = sheets_api.get_subcategories_for_category(current_category)
            subcategories_data = data['new_campaign'].get('subcategories', {})
            selected_list = subcategories_data.get(current_category, [])

            # Convert index to subcategory name
            try:
                idx = int(value_to_toggle)
                if 0 <= idx < len(subcategories):
                    subcategory_name = subcategories[idx]['name']
                    if subcategory_name in selected_list:
                        selected_list.remove(subcategory_name)
                    else:
                        selected_list.append(subcategory_name)
                else:
                    await callback.answer("Invalid selection.", show_alert=True)
                    return
            except (ValueError, IndexError):
                await callback.answer("Invalid selection.", show_alert=True)
                return

            subcategories_data[current_category] = selected_list
            new_campaign['subcategories'] = subcategories_data
            await state.update_data(new_campaign=new_campaign)

            # Redraw keyboard for current category with indices
            options = [(sub['name'], str(idx)) for idx, sub in enumerate(subcategories)]
            selected_indices = [str(idx) for idx, sub in enumerate(subcategories) if sub['name'] in selected_list]

            progress_text = f"<b>Категория {current_index + 1}/{len(selected_categories)}: {current_category}</b>\n\n"
            progress_text += "Выберите подкатегории (или 'Выбрать все' для всей категории):"

            await callback.message.edit_reply_markup(
                reply_markup=get_multiselect_keyboard(
                    options=options,
                    selected_values=selected_indices,
                    done_callback=f"campaign_done_subcategories:{current_index}",
                    back_callback="back_to_categories_from_subcategories"
                )
            )
        await callback.answer()
        return
    elif current_state == CampaignStates.campaign_new_select_rating:
        key = 'ratings'
        options_sheet = 'ratings'  # This would be a hardcoded list, but we'll handle it differently
    elif current_state == CampaignStates.campaign_new_select_language:
        key = 'languages'
        options_sheet = 'languages'
    else:
        await callback.answer("Ошибка состояния.", show_alert=True)
        return

    # Для категорий, value_to_toggle - это имя категории.
    # Нам нужно получить индекс для отображения в клавиатуре.
    if key == 'categories':
        all_categories = sheets_api.get_unique_categories()
        try:
            category_name = value_to_toggle
            idx = next((i for i, cat in enumerate(all_categories) if cat['name'] == category_name), -1)
            if idx != -1:
                selected_list = new_campaign.get(key, [])
                if category_name in selected_list:
                    selected_list.remove(category_name)
                else:
                    selected_list.append(category_name)
                new_campaign[key] = selected_list
            else:
                await callback.answer("Неверный выбор.", show_alert=True)
                return
        except (ValueError, IndexError):
            await callback.answer("Неверный выбор.", show_alert=True)
            return
    else:
        # Старая логика для других состояний
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
            ("3.5+ звёзд", "3.5"),
            ("4.0+ звёзд", "4.0"),
            ("4.5+ звёзд", "4.5"),
            ("4.8+ звёзд", "4.8")
        ]
        done_callback = "campaign_done_rating"
        back_callback = "campaign_done_categories"
    elif key == 'languages':
        options = await get_options_from_gsheets(options_sheet)
        done_callback = "campaign_done_language"
        back_callback = "campaign_done_rating"
    else:
        options = await get_options_from_gsheets(options_sheet)
        # Определяем нужный done_callback (для каждой кнопки он свой)
        if key == 'channels': done_callback = "campaign_done_channels"
        elif key == 'categories': done_callback = "campaign_done_categories"
        elif key == 'subcategories': done_callback = "campaign_done_subcategories"

        # Определяем нужный back_callback
        if key == 'channels': back_callback = "back_to_campaign_menu"
        elif key == 'categories': back_callback = "campaign_new_start" # Go back to the start of channel selection
        elif key == 'subcategories': back_callback = "back_to_categories_from_subcategories" # Go back to category selection

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
        # Handle select all for current category subcategories
        current_index = data['new_campaign'].get('current_category_index', 0)
        selected_categories = data['new_campaign']['categories']
        if current_index < len(selected_categories):
            current_category = selected_categories[current_index]
            subcategories = sheets_api.get_subcategories_for_category(current_category)
            all_values = [sub['name'] for sub in subcategories]

            subcategories_data = data['new_campaign'].get('subcategories', {})
            selected_list = subcategories_data.get(current_category, [])

            if len(selected_list) == len(all_values):
                # If all selected, deselect all
                subcategories_data[current_category] = []
            else:
                # Select all
                subcategories_data[current_category] = all_values

            new_campaign['subcategories'] = subcategories_data
            await state.update_data(new_campaign=new_campaign)

            # Redraw keyboard with indices
            options = [(sub['name'], str(idx)) for idx, sub in enumerate(subcategories)]
            selected_indices = [str(idx) for idx, sub in enumerate(subcategories) if sub['name'] in subcategories_data[current_category]]
            progress_text = f"<b>Категория {current_index + 1}/{len(selected_categories)}: {current_category}</b>\n\n"
            progress_text += "Выберите подкатегории (или 'Выбрать все' для всей категории):"

            await callback.message.edit_reply_markup(
                reply_markup=get_multiselect_keyboard(
                    options=options,
                    selected_values=selected_indices,
                    done_callback=f"campaign_done_subcategories:{current_index}",
                    back_callback="back_to_categories_from_subcategories"
                )
            )
        await callback.answer()
        return
    elif current_state == CampaignStates.campaign_new_select_rating:
        key = 'ratings'
        # Hardcoded options for rating
        options = [
            ("3.5+ звёзд", "3.5"),
            ("4.0+ звёзд", "4.0"),
            ("4.5+ звёзд", "4.5"),
            ("4.8+ звёзд", "4.8")
        ]
        done_callback = "campaign_done_rating"
        back_callback = "campaign_done_categories"
    elif current_state == CampaignStates.campaign_new_select_language:
        key = 'languages'
        options_sheet = 'languages'
        done_callback = "campaign_done_language"
        back_callback = "campaign_done_rating"
    else:
        await callback.answer("Ошибка состояния.", show_alert=True)
        return

    if key == 'ratings':
        # Already have options defined above
        all_values = [val for name, val in options]
    elif key == 'categories':
        options = await get_options_from_gsheets(options_sheet)
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
        # Collect all selected subcategory node_ids for PA API search
        selected_browse_nodes = []
        subcategories_data = campaign_data.get('subcategories', {})

        for category_name, subcategories in subcategories_data.items():
            if subcategories:  # Only if subcategories were selected for this category
                # Get node_ids for selected subcategories
                all_subs = sheets_api.get_subcategories_for_category(category_name)
                sub_dict = {sub['name']: sub['node_id'] for sub in all_subs}

                for sub_name in subcategories:
                    if sub_name in sub_dict:
                        selected_browse_nodes.append(sub_dict[sub_name])

        # If no subcategories selected, use category node_ids as fallback
        if not selected_browse_nodes:
            for category in campaign_data.get('categories', []):
                categories_data = sheets_api.get_categories_subcategories()
                for item in categories_data:
                    if item['category'] == category:
                        selected_browse_nodes.append(item['node_id_category'])
                        break

        # Remove duplicates
        selected_browse_nodes = list(set(selected_browse_nodes))
        campaign_data['browse_node_ids'] = selected_browse_nodes

        # Legacy support - add categories_with_nodes for backward compatibility
        categories_with_nodes = []
        for category in campaign_data.get('categories', []):
            categories_data = sheets_api.get_categories_subcategories()
            category_node = None
            for item in categories_data:
                if item['category'] == category:
                    category_node = item['node_id_category']
                    break

            categories_with_nodes.append({
                'name': category,
                'browse_node_id': category_node or '2892859031'  # Default fallback
            })

        campaign_data['categories_with_nodes'] = categories_with_nodes

        # Проверка уникальности
        campaign_mgr = get_campaign_manager()
        if campaign_mgr is None:
            raise Exception("Campaign manager not initialized")
        campaign_name = campaign_data['name']  # Store name before it gets popped
        is_unique = await campaign_mgr.is_name_unique(campaign_name)
        if not is_unique:
            await callback.answer(f"⚠️ Кампания с названием '{campaign_name}' уже существует. Измените название.", show_alert=True)
            # Возвращаемся на шаг ввода названия
            await state.set_state(CampaignStates.campaign_new_input_name)
            await callback.message.edit_text("Пожалуйста, введите другое, уникальное название для новой кампании:")
            return

        campaign_id = await campaign_mgr.save_new_campaign(campaign_data)

        await callback.message.edit_text(
            f"🎉 Кампания <b>'{campaign_name}'</b> успешно создана с ID: {campaign_id}.\n"
            f"Текущий статус: <b>Не выбраны тайминги</b>.\n\n"
            "Вы можете продолжить работу в Главном меню.",
            parse_mode="HTML"
        )

        # Сброс FSM и переход в меню кампаний
        await state.clear()
        # Возвращаемся в меню кампаний, чтобы увидеть новую кампанию
        await enter_campaign_module(callback, state)

    except Exception as e:
        await callback.message.edit_text(f"❌ Критическая ошибка при сохранении кампании: {e}")
        await state.clear()

    await callback.answer()

# Хэндлер для кнопки "назад" в меню кампаний
from handlers.campaigns.manage import enter_campaign_module
router.callback_query(F.data == "back_to_campaign_menu")(enter_campaign_module)
