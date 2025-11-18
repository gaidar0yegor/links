# states/campaign_states.py
from aiogram.fsm.state import State, StatesGroup

class CampaignStates(StatesGroup):
    # Main states
    in_main_menu = State()
    in_campaign_menu = State()

    # Состояния для создания кампании
    campaign_new_start = State()
    campaign_new_select_channel = State()
    campaign_new_select_category = State()
    campaign_new_select_subcategory = State()
    campaign_new_select_rating = State()
    campaign_new_select_language = State()
    campaign_new_input_name = State()
    campaign_new_review = State()

    # Состояния для управления существующей кампанией
    campaign_edit_main = State()

    # New states for multi-day timing selection
    timing_select_days = State()
    timing_input_start = State()
    timing_input_end = State()

    # New states for advanced filters
    campaign_new_input_min_price = State()
    campaign_new_input_min_saving_percent = State()
    campaign_new_select_fba = State()
    campaign_new_input_max_sales_rank = State()

    # State for delete confirmation
    delete_confirmation = State()
