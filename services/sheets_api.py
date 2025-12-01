# services/sheets_api.py
import gspread
import time
from google.oauth2.service_account import Credentials
from config import conf # Используем конфигурацию из config.py
from gspread.exceptions import WorksheetNotFound, SpreadsheetNotFound


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    Выполняет функцию с повторными попытками и экспоненциальной задержкой.
    
    Args:
        func: Функция для выполнения (callable)
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка в секундах (удваивается с каждой попыткой)
    
    Returns:
        Результат выполнения функции
    
    Raises:
        Exception: Если все попытки исчерпаны
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func()
        except WorksheetNotFound:
            # Не ретраим если листа просто нет
            raise
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = base_delay * (2 ** attempt)  # 1, 2, 4 секунды
                print(f"⚠️ Google Sheets retry {attempt + 1}/{max_retries} after {wait_time:.1f}s: {type(e).__name__}")
                time.sleep(wait_time)
            else:
                print(f"❌ Google Sheets failed after {max_retries} retries: {e}")
    raise last_exception

class GoogleSheetsAPI:
    """Класс для работы с Google Sheets через сервисный аккаунт."""
    def __init__(self):
        self.available = False
        try:
            # Настройка scopes для Google Sheets API
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

            # Создание credentials из service account файла
            creds = Credentials.from_service_account_file(conf.gsheets.service_account_file, scopes=scopes)

            # Авторизация и открытие таблицы
            self.gc = gspread.authorize(creds)
            self.spreadsheet = self.gc.open_by_key(conf.gsheets.spreadsheet_id)
            self.available = True
            print("✅ Google Sheets API initialized successfully with service account")
        except FileNotFoundError:
            print(f"⚠️  GSheets service account key file not found: {conf.gsheets.service_account_file}. Using dummy data for testing.")
        except SpreadsheetNotFound:
            print(f"⚠️  Google Sheet not found with ID: {conf.gsheets.spreadsheet_id}. Using dummy data for testing.")
        except Exception as e:
            print(f"⚠️  Failed to initialize Google Sheets API: {e}. Using dummy data for testing.")

    def get_whitelist(self) -> list[int]:
        """Получает список авторизованных Telegram ID из таблицы users_whitelist."""
        if not self.available:
            # Return dummy whitelist for testing
            print("Using dummy whitelist for testing")
            return [123456789, 1451953302, 117422597, 954096177]  # Dummy user IDs + authorized users

        try:
            # Получаем лист 'users_whitelist'
            worksheet = self.spreadsheet.worksheet("users_whitelist")
            # Получаем все значения из первого столбца (предполагаем, что там ID)
            # Примечание: ID должны быть целыми числами, поэтому фильтруем пустые и конвертируем.
            all_values = worksheet.col_values(1)

            # Конвертируем в int и возвращаем
            whitelist = [int(v) for v in all_values if v.isdigit()]
            return whitelist
        except WorksheetNotFound:
            print("WARNING: Worksheet 'users_whitelist' not found. Check sheet name.")
            return []
        except Exception as e:
            print(f"Error reading whitelist: {e}")
            return []

    def get_users_for_notification(self) -> list[int]:
        """
        Получает список Telegram ID пользователей, у которых включены уведомления.
        Ожидает колонки: [Telegram ID, ..., Notification (Yes/No)]
        Предполагаем, что Notification - это, например, 3-я колонка (индекс 2), или ищем по заголовку.
        Для надежности будем искать заголовок 'notification'.
        """
        if not self.available:
            # Dummy data: only 117422597 wants notifications
            print("Using dummy notification list for testing")
            return [117422597]

        try:
            worksheet = self.spreadsheet.worksheet("users_whitelist")
            data = worksheet.get_all_values()

            if not data:
                return []

            headers = [h.lower() for h in data[0]]
            try:
                id_idx = 0 # Обычно ID в первой колонке
                # Попытаемся найти колонку 'notification'
                notify_idx = headers.index('notification')
            except ValueError:
                print("⚠️ Column 'notification' not found in users_whitelist")
                return []

            notify_users = []
            for row in data[1:]: # Пропускаем заголовок
                if len(row) > notify_idx and len(row) > id_idx:
                    user_id_str = row[id_idx]
                    notify_val = row[notify_idx].strip().lower()

                    if user_id_str.isdigit() and notify_val in ['yes', 'true', '1', '+']:
                        notify_users.append(int(user_id_str))

            return notify_users

        except WorksheetNotFound:
            print("WARNING: Worksheet 'users_whitelist' not found.")
            return []
        except Exception as e:
            print(f"Error getting notification users: {e}")
            return []

    def get_sheet_data(self, sheet_name: str) -> list[list[str]]:
        """Общий метод для получения данных из любой таблицы с retry логикой."""
        if not self.available:
            # Return dummy data for testing
            if sheet_name == "rewrite_prompt":
                return [["Prompt", "Link_format"], ["Rewrite the following text to make it engaging and persuasive and fit for a social media post.", "🔜 Acquista ora"]]
            elif sheet_name == "statistics":
                return [["Date", "Revenue", "Clicks", "Sales"], ["2024-01-01", "1000", "500", "50"]]
            elif sheet_name == "utm_marks":
                return [["utm_source", "social_media"], ["utm_medium", "telegram_bot"], ["utm_campaign", "affiliate"]]
            else:
                return []

        try:
            # Используем retry для устойчивости к временным сетевым ошибкам
            def fetch_data():
                worksheet = self.spreadsheet.worksheet(sheet_name)
                return worksheet.get_all_values()
            
            return _retry_with_backoff(fetch_data, max_retries=3, base_delay=1.0)
        except WorksheetNotFound:
            print(f"WARNING: Worksheet '{sheet_name}' not found.")
            return []
        except Exception as e:
            print(f"Error reading sheet '{sheet_name}': {e}")
            return []

    def get_link_format(self) -> str:
        """Получает формат текста ссылки из таблицы rewrite_prompt (колонка Link_format)."""
        if not self.available:
            return "🔜 Acquista ora"  # Default for testing
        
        try:
            data = self.get_sheet_data("rewrite_prompt")
            # Ожидаем: [["Prompt", "Link_format"], ["prompt text...", "🔜 Acquista ora"]]
            if data and len(data) > 1 and len(data[1]) > 1:
                link_format = data[1][1].strip()
                if link_format:
                    return link_format
            return "🔜 Acquista ora"  # Default fallback
        except Exception as e:
            print(f"Error reading link format: {e}")
            return "🔜 Acquista ora"

    def get_utm_marks(self) -> dict:
        """Получает UTM метки из таблицы utm_marks."""
        if not self.available:
            # Return dummy UTM marks for testing
            return {
                "utm_source": "social_media",
                "utm_medium": "telegram_bot",
                "utm_campaign": "affiliate"
            }

        try:
            data = self.get_sheet_data("utm_marks")
            utm_dict = {}
            for row in data[1:]:  # Skip header
                if len(row) >= 2:
                    utm_dict[row[0]] = row[1]
            return utm_dict
        except Exception as e:
            print(f"Error reading UTM marks: {e}")
            return {}

    def get_channel_tracking_ids(self) -> dict:
        """Получает tracking IDs для каналов из таблицы channels."""
        if not self.available:
            # Return dummy channel tracking IDs for testing
            return {
                "@CheapAmazon3332234": "tg_bot_main",
                "@test_channel": "tg_bot_test"
            }

        try:
            data = self.get_sheet_data("channels")
            channel_tracking = {}
            for row in data[1:]:  # Skip header, expect columns: channel_name, tracking_id
                if len(row) >= 2 and row[0] and row[1]:
                    channel_tracking[row[0]] = row[1]
            return channel_tracking
        except Exception as e:
            print(f"Error reading channel tracking IDs: {e}")
            return {}

    def get_categories_subcategories(self) -> list[dict]:
        """Получает объединенные данные категорий и подкатегорий."""
        if not self.available:
            # Return dummy data for testing
            return [
                {
                    "category": "Apparel",
                    "category_ru": "Одежда",
                    "node_id_category": "2892859031",
                    "subcategory": "Abbigliamento da notte, lingerie e intimo",
                    "subcategory_ru": "Ночное белье, нижнее белье и интим",
                    "node_id_subcategory": "21695399031",
                    "comission_percent": "12"
                },
                {
                    "category": "Apparel",
                    "category_ru": "Одежда",
                    "node_id_category": "2892859031",
                    "subcategory": "Abbigliamento premaman",
                    "subcategory_ru": "Одежда для беременных",
                    "node_id_subcategory": "1806562031",
                    "comission_percent": "12"
                }
            ]

        try:
            data = self.get_sheet_data("categories_subcategories")
            categories = []
            for row in data[1:]:  # Skip header
                if len(row) >= 6:  # category, category_ru, node_id_category, subcategory, subcategory_ru, node_id_subcategory
                    item = {
                        "category": row[0],
                        "category_ru": row[1],
                        "node_id_category": row[2],
                        "subcategory": row[3],
                        "subcategory_ru": row[4],
                        "node_id_subcategory": row[5]
                    }
                    # Check for Comission_percent (7th column, index 6)
                    if len(row) >= 7:
                         item["comission_percent"] = row[6]
                    else:
                         item["comission_percent"] = ""
                    
                    categories.append(item)
            return categories
        except Exception as e:
            print(f"Error reading categories_subcategories: {e}")
            return []

    def get_unique_categories(self) -> list[dict]:
        """Получает уникальные категории из объединенной таблицы (на русском)."""
        categories_data = self.get_categories_subcategories()
        unique_categories = {}

        for item in categories_data:
            # Use the translated category name as name, but keep original for lookups
            category_display_name = item["category_ru"]
            category_key = item["category"]  # Always use Italian as key for internal consistency
            if category_key not in unique_categories:
                unique_categories[category_key] = {
                    "name": category_display_name,
                    "node_id": item["node_id_category"],
                    "original_name": item["category"],  # Keep original for mapping
                    "comission_percent": item.get("comission_percent", "") # Add commission percent
                }

        return list(unique_categories.values())

    def get_subcategories_for_category(self, category_name: str) -> list[dict]:
        """Получает подкатегории для указанной категории (на русском)."""
        categories_data = self.get_categories_subcategories()
        subcategories = []

        for item in categories_data:
            # Match by original category name (Italian)
            if item["category"] == category_name:
                subcategory_display_name = item["subcategory_ru"]
                subcategories.append({
                    "name": subcategory_display_name,
                    "node_id": item["node_id_subcategory"],
                    "original_name": item["subcategory"]  # Keep original for mapping
                })

        return subcategories

    def get_track_ids(self) -> list[dict]:
        """Получает Track IDs из таблицы TrackIDs. Колонки: Tracker, NameTrack_id."""
        if not self.available:
            # Return dummy data for testing
            return [
                {"tracker": "telegram_main", "name": "Основной Telegram"},
                {"tracker": "telegram_test", "name": "Тестовый канал"}
            ]

        try:
            data = self.get_sheet_data("TrackIDs")
            track_ids = []
            for row in data[1:]:  # Skip header
                if len(row) >= 2 and row[0]:
                    track_ids.append({
                        "tracker": row[0],  # Tracker (value to use)
                        "name": row[1] if row[1] else row[0]  # NameTrack_id (display name)
                    })
            return track_ids
        except Exception as e:
            print(f"Error reading TrackIDs: {e}")
            return []

# Создай глобальный экземпляр для использования в хэндлерах
sheets_api = GoogleSheetsAPI()
