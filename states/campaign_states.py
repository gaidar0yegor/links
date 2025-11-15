# states/campaign_states.py
from aiogram.fsm.state import State, StatesGroup

class CampaignStates(StatesGroup):
    """Состояния для управления диалогами создания и редактирования кампаний."""
    # Главное состояние модуля "Рекламные кампании"
    in_campaign_menu = State()

    # Состояния для создания новой кампании (2.3.2)
    campaign_new_start = State() # Точка входа
    campaign_new_select_channel = State() # 1. Выбор канала
    campaign_new_select_category = State() # 2. Выбор категории
    campaign_new_select_subcategory = State() # 3. Выбор подкатегорий

    campaign_new_select_rating = State() # 4. Выбор рейтинга
    campaign_new_select_language = State() # 5. Выбор языка
    campaign_new_input_name = State() # 6. Ввод названия
    campaign_new_review = State() # (Не по ТЗ, но полезно) Обзор перед сохранением

    # Состояния для редактирования существующей кампании
    campaign_edit_main = State() # Основное меню редактирования кампании

    # Состояния для установки таймингов (2.4)
    campaign_timing_select_day = State() # Выбор дня недели
    campaign_timing_input_start = State() # Ввод времени начала
    campaign_timing_input_end = State() # Ввод времени окончания
