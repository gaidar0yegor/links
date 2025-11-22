# services/sheets_api.py
import gspread
from google.oauth2.service_account import Credentials
from config import conf # Используем конфигурацию из config.py
from gspread.exceptions import WorksheetNotFound, SpreadsheetNotFound

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

    def get_sheet_data(self, sheet_name: str) -> list[list[str]]:
        """Общий метод для получения данных из любой таблицы."""
        if not self.available:
            # Return dummy data for testing
            if sheet_name == "rewrite_prompt":
                return [["Prompt"], ["Rewrite the following text to make it engaging and persuasive and fit for a social media post."]]
            elif sheet_name == "statistics":
                return [["Date", "Revenue", "Clicks", "Sales"], ["2024-01-01", "1000", "500", "50"]]
            elif sheet_name == "utm_marks":
                return [["utm_source", "social_media"], ["utm_medium", "telegram_bot"], ["utm_campaign", "affiliate"]]
            else:
                return []

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            # Возвращаем все данные листа
            return worksheet.get_all_values()
        except WorksheetNotFound:
            print(f"WARNING: Worksheet '{sheet_name}' not found.")
            return []
        except Exception as e:
            print(f"Error reading sheet '{sheet_name}': {e}")
            return []

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

    def get_categories_subcategories(self, language: str = 'it') -> list[dict]:
        """Получает объединенные данные категорий и подкатегорий с учетом языка."""
        if not self.available:
            # Return dummy data for testing
            return [
                {
                    "category": "Apparel",
                    "category_ru": "Одежда",
                    "node_id_category": "2892859031",
                    "subcategory": "Abbigliamento da notte, lingerie e intimo",
                    "subcategory_ru": "Ночное белье, нижнее белье и интим",
                    "node_id_subcategory": "21695399031"
                },
                {
                    "category": "Apparel",
                    "category_ru": "Одежда",
                    "node_id_category": "2892859031",
                    "subcategory": "Abbigliamento premaman",
                    "subcategory_ru": "Одежда для беременных",
                    "node_id_subcategory": "1806562031"
                }
            ]

        try:
            data = self.get_sheet_data("categories_subcategories")
            categories = []
            for row in data[1:]:  # Skip header
                if len(row) >= 6:  # category, category_ru, node_id_category, subcategory, subcategory_ru, node_id_subcategory
                    categories.append({
                        "category": row[0] if language == 'it' else row[1],  # Always include original for internal use
                        "category_ru": row[1],
                        "node_id_category": row[2],
                        "subcategory": row[3] if language == 'it' else row[4],
                        "subcategory_ru": row[4],
                        "node_id_subcategory": row[5]
                    })
            return categories
        except Exception as e:
            print(f"Error reading categories_subcategories: {e}")
            return []

    def get_unique_categories(self, language: str = 'it') -> list[dict]:
        """Получает уникальные категории из объединенной таблицы с учетом языка."""
        categories_data = self.get_categories_subcategories(language)
        unique_categories = {}

        for item in categories_data:
            # Use the translated category name as name, but keep original for lookups
            category_display_name = item["category_ru"] if language == 'ru' else item["category"]
            category_key = item["category"]  # Always use Italian as key for internal consistency
            if category_key not in unique_categories:
                unique_categories[category_key] = {
                    "name": category_display_name,
                    "node_id": item["node_id_category"],
                    "original_name": item["category"]  # Keep original for mapping
                }

        return list(unique_categories.values())

    def get_subcategories_for_category(self, category_name: str, language: str = 'it') -> list[dict]:
        """Получает подкатегории для указанной категории с учетом языка."""
        categories_data = self.get_categories_subcategories(language)
        subcategories = []

        for item in categories_data:
            # Match by original category name (Italian)
            if item["category"] == category_name:
                subcategory_display_name = item["subcategory_ru"] if language == 'ru' else item["subcategory"]
                subcategories.append({
                    "name": subcategory_display_name,
                    "node_id": item["node_id_subcategory"],
                    "original_name": item["subcategory"]  # Keep original for mapping
                })

        return subcategories

# Создай глобальный экземпляр для использования в хэндлерах
sheets_api = GoogleSheetsAPI()
