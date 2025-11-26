# services/sheets_api.py
import gspread
from google.oauth2.service_account import Credentials
from config import conf # Используем конфигурацию из config.py
from gspread.exceptions import WorksheetNotFound, SpreadsheetNotFound
import pandas as pd
from typing import Union, List
import io # Imported at top level

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

    def upload_csv_to_sheet(self, sheet_name: str, csv_content: Union[str, pd.DataFrame], max_columns: int = None) -> bool:
        """
        Загружает содержимое CSV (или DataFrame) в указанный лист Google Sheets.
        Очищает только колонки с данными (A-M), сохраняя формулы в N-Z.
        
        Args:
            sheet_name: Имя листа (например, 'statistics_clicks' или 'statistics_orders')
            csv_content: Содержимое CSV в виде строки или pandas DataFrame
            max_columns: Максимальное количество колонок для загрузки (и очистки). 
                         Если CSV шире, лишние колонки будут обрезаны.
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.available:
            print(f"⚠️ Google Sheets API not available. Skipping upload to {sheet_name}")
            return False

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            
            # Prepare data
            df = None
            if isinstance(csv_content, pd.DataFrame):
                df = csv_content
            else:
                # Assuming csv_content is a string
                import csv
                
                content_io = io.StringIO(csv_content)
                lines = content_io.readlines()
                
                if not lines:
                    print(f"⚠️ Empty CSV content")
                    return True

                # Heuristic to find the header row and separator
                start_row = 0
                sep = ','
                max_cols = 0
                
                # Check first 20 lines to find the best separator and header row
                for i, line in enumerate(lines[:20]):
                    # Count potential separators
                    commas = line.count(',')
                    semicolons = line.count(';')
                    tabs = line.count('\t')
                    
                    # Find the max separators
                    current_max = max(commas, semicolons, tabs)
                    
                    if current_max > max_cols:
                        max_cols = current_max
                        start_row = i
                        if commas == current_max:
                            sep = ','
                        elif semicolons == current_max:
                            sep = ';'
                        elif tabs == current_max:
                            sep = '\t'
                
                print(f"📊 Detected CSV format: start_row={start_row}, sep='{sep}'")
                
                # Reset pointer
                content_io.seek(0)
                
                # Read with detected settings
                try:
                    df = pd.read_csv(content_io, sep=sep, skiprows=start_row)
                except Exception as parse_error:
                    print(f"⚠️ Pandas parsing failed, trying python engine: {parse_error}")
                    content_io.seek(0)
                    df = pd.read_csv(content_io, sep=sep, skiprows=start_row, engine='python')

            if df is None:
                print(f"⚠️ Failed to parse CSV data")
                return False
            
            # Slice dataframe to max_columns if provided
            if max_columns is not None:
                print(f"✂️ Limiting columns to {max_columns}")
                df = df.iloc[:, :max_columns]

            # Format numeric columns
            if not df.empty:
                for col in df.columns:
                    # Only attempt conversion if object/string type
                    if df[col].dtype == 'object':
                        try:
                            cleaned_col = df[col].astype(str).str.replace('€', '').str.replace('$', '').str.strip()
                            
                            # Check if it looks like EU number format
                            if cleaned_col.str.contains(',').any():
                                converted = cleaned_col.str.replace('.', '').str.replace(',', '.')
                                df[col] = pd.to_numeric(converted, errors='ignore')
                            else:
                                df[col] = pd.to_numeric(cleaned_col, errors='ignore')
                        except Exception:
                            pass 

            # Convert to list of lists for upload
            data_to_upload = df.where(pd.notnull(df), '').values.tolist()

            if not data_to_upload:
                print(f"⚠️ No data to upload to {sheet_name}")
                return True

            # Calculate range to clear based on data width
            # Assuming we clear columns A up to the width of the new data
            num_rows = 50000  # Safe upper limit
            num_cols = len(df.columns)
            
            # Convert column number to letter (1 -> A, 2 -> B, etc.)
            # Simple implementation for A-Z (1-26) which covers our case (M is 13)
            if num_cols <= 26:
                end_col_letter = chr(ord('A') + num_cols - 1)
            else:
                # Fallback for wider tables (AA, AB, etc.) - unlikely here but safe default
                end_col_letter = 'M' 

            clear_range = f'A2:{end_col_letter}{num_rows}'
            print(f"🧹 Clearing range {clear_range} to preserve formulas in later columns")

            # Clear ONLY the data columns, preserving formulas in N, O, P...
            try:
                worksheet.batch_clear([clear_range])
            except Exception as e:
                print(f"⚠️ Error clearing sheet {sheet_name}: {e}")
                pass

            # Append new data starting from row 2
            worksheet.update(range_name='A2', values=data_to_upload, value_input_option='USER_ENTERED')
            
            print(f"✅ Successfully uploaded {len(data_to_upload)} rows to {sheet_name}")
            return True

        except WorksheetNotFound:
            print(f"❌ Worksheet '{sheet_name}' not found. Please create it first.")
            return False
        except Exception as e:
            print(f"❌ Error uploading to {sheet_name}: {e}")
            return False

# Создай глобальный экземпляр для использования в хэндлерах
sheets_api = GoogleSheetsAPI()
