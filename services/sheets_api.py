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

# Создай глобальный экземпляр для использования в хэндлерах
sheets_api = GoogleSheetsAPI()
