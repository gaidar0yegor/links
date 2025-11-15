# services/amazon_paapi_client.py
import aiohttp
import hashlib
import hmac
import json
from datetime import datetime
from typing import Dict, Any, Optional
from config import conf
from services.logger import bot_logger

class AmazonPAAPIClient:
    """Асинхронный клиент для Amazon Product Advertising API 5.0 с AWS Signature V4."""

    def __init__(self):
        self.access_key = conf.amazon.access_key
        self.secret_key = conf.amazon.secret_key
        self.associate_tag = conf.amazon.associate_tag
        self.region = conf.amazon.region
        self.marketplace = conf.amazon.marketplace
        self.service = "ProductAdvertisingAPI"
        self.host = "webservices.amazon.com"
        self.endpoint = f"https://{self.host}/paapi5/searchitems"

        # Check if Amazon API is disabled (for Google Sheets-only mode)
        self.use_amazon_api = getattr(conf.amazon, 'use_api', True)
        if isinstance(self.use_amazon_api, str):
            self.use_amazon_api = self.use_amazon_api.lower() in ('true', '1', 'yes', 'on')

        # Инициализируем aiohttp сессию
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _get_signature_key(self, key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
        """Генерирует ключ для подписи по алгоритму AWS Signature Version 4."""
        k_date = hmac.new(f"AWS4{key}".encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region_name.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service_name.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, "aws4_request".encode('utf-8'), hashlib.sha256).digest()
        return k_signing

    def _sign_request(self, payload: str, amz_date: str, date_stamp: str) -> str:
        """Создает подпись для запроса по алгоритму AWS Signature Version 4."""

        # 1. Создаем canonical request
        canonical_uri = "/paapi5/searchitems"
        canonical_querystring = ""
        canonical_headers = f"host:{self.host}\nx-amz-date:{amz_date}\n"
        signed_headers = "host;x-amz-date"
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

        canonical_request = "\n".join([
            "POST",
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash
        ])

        # 2. Создаем string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()

        string_to_sign = "\n".join([
            algorithm,
            amz_date,
            credential_scope,
            canonical_request_hash
        ])

        # 3. Вычисляем подпись
        signing_key = self._get_signature_key(self.secret_key, date_stamp, self.region, self.service)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # 4. Создаем заголовок Authorization
        authorization_header = (
            f"{algorithm} Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return authorization_header

    async def search_items(self, keywords: str, min_rating: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Выполняет поиск товаров через Amazon PA API 5.0 или возвращает mock данные.

        Args:
            keywords: Ключевые слова для поиска
            min_rating: Минимальный рейтинг товара

        Returns:
            Словарь с данными товара или None в случае ошибки
        """
        # If Amazon API is disabled, return mock data
        if not self.use_amazon_api:
            return self._get_mock_product_data(keywords, min_rating)

        if not self.session:
            self.session = aiohttp.ClientSession()

        # Создаем timestamp для подписи
        now = datetime.utcnow()
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')

        # Создаем payload для запроса
        payload = {
            "Keywords": keywords,
            "SearchIndex": "All",
            "ItemCount": 1,  # Получаем только один товар
            "Resources": [
                "ItemInfo.Title",
                "Images.Primary.Large",
                "Offers.Listings.Price",
                "ItemInfo.Features",
                "ItemInfo.ProductInfo"
            ],
            "PartnerTag": self.associate_tag,
            "PartnerType": "Associates",
            "Marketplace": self.marketplace
        }

        # Добавляем фильтр по рейтингу, если указан
        if min_rating > 0:
            payload["MinReviewsRating"] = min_rating

        payload_json = json.dumps(payload)

        # Создаем подпись
        authorization_header = self._sign_request(payload_json, amz_date, date_stamp)

        # Создаем заголовки
        headers = {
            "Authorization": authorization_header,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Amz-Date": amz_date,
            "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
            "Content-Encoding": "amz-1.0"
        }

        try:
            # Выполняем запрос
            async with self.session.post(
                self.endpoint,
                data=payload_json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    bot_logger.log_error(
                        "AmazonPAAPIClient",
                        Exception(f"HTTP {response.status}: {error_text}"),
                        f"Keywords: {keywords}"
                    )
                    return None

                data = await response.json()

                # Проверяем на ошибки в ответе
                if "Errors" in data:
                    error = data["Errors"][0]
                    bot_logger.log_error(
                        "AmazonPAAPIClient",
                        Exception(f"API Error: {error.get('Code', 'Unknown')} - {error.get('Message', 'Unknown')}"),
                        f"Keywords: {keywords}"
                    )
                    return None

                # Извлекаем данные товара
                items = data.get("SearchResult", {}).get("Items", [])
                if not items:
                    bot_logger.log_error(
                        "AmazonPAAPIClient",
                        Exception("No items found"),
                        f"Keywords: {keywords}"
                    )
                    return None

                item = items[0]  # Берем первый товар

                # Извлекаем нужные поля
                title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "No Title")
                image_url = item.get("Images", {}).get("Primary", {}).get("Large", {}).get("URL", "")
                detail_page_url = item.get("DetailPageURL", "")

                # Получаем ASIN
                asin = item.get("ASIN", "")

                return {
                    "ASIN": asin,
                    "Title": title,
                    "ImageURL": image_url,
                    "AffiliateLink": detail_page_url
                }

        except aiohttp.ClientError as e:
            bot_logger.log_error(
                "AmazonPAAPIClient",
                e,
                f"Network error for keywords: {keywords}"
            )
            return None
        except Exception as e:
            bot_logger.log_error(
                "AmazonPAAPIClient",
                e,
                f"Unexpected error for keywords: {keywords}"
            )
            return None

    def _get_mock_product_data(self, keywords: str, min_rating: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Returns product data from Google Sheets for Sheets-only mode.

        Args:
            keywords: Search keywords (used to filter products)
            min_rating: Minimum rating filter

        Returns:
            Product data dictionary from Google Sheets
        """
        try:
            from services.sheets_api import sheets_api

            # Get products from Google Sheets
            products_data = sheets_api.get_sheet_data('products')

            if not products_data or len(products_data) < 2:  # No data or only headers
                bot_logger.log_error(
                    "AmazonPAAPIClient",
                    Exception("No products found in Google Sheets"),
                    "Using fallback mock data"
                )
                return self._get_fallback_mock_data(keywords, min_rating)

            # Parse headers
            headers = products_data[0]
            if len(headers) < 11:
                bot_logger.log_error(
                    "AmazonPAAPIClient",
                    Exception("Invalid products worksheet format"),
                    "Using fallback mock data"
                )
                return self._get_fallback_mock_data(keywords, min_rating)

            # Create column index mapping
            col_indices = {header: idx for idx, header in enumerate(headers)}

            # Filter products by keywords and rating
            matching_products = []
            for row in products_data[1:]:  # Skip header
                if len(row) < len(headers):
                    continue

                # Check if product is active
                active = row[col_indices.get('active', -1)].upper() if col_indices.get('active', -1) >= 0 else 'TRUE'
                if active != 'TRUE':
                    continue

                # Check rating filter
                try:
                    rating = float(row[col_indices.get('rating', -1)]) if col_indices.get('rating', -1) >= 0 else 4.0
                    if rating < min_rating:
                        continue
                except (ValueError, IndexError):
                    continue

                # Check keyword match in name or description
                name = row[col_indices.get('name', -1)].lower() if col_indices.get('name', -1) >= 0 else ''
                description = row[col_indices.get('description', -1)].lower() if col_indices.get('description', -1) >= 0 else ''

                if keywords.lower() in name or keywords.lower() in description:
                    matching_products.append(row)

            # If no matches, return any active product
            if not matching_products:
                matching_products = [row for row in products_data[1:]
                                   if len(row) >= len(headers) and
                                   (row[col_indices.get('active', -1)].upper() if col_indices.get('active', -1) >= 0 else 'TRUE') == 'TRUE']

            if not matching_products:
                return self._get_fallback_mock_data(keywords, min_rating)

            # Select a random matching product
            import random
            selected_product = random.choice(matching_products)

            # Extract product data
            product_id = selected_product[col_indices.get('id', 0)] if col_indices.get('id', -1) >= 0 else 'UNKNOWN'
            name = selected_product[col_indices.get('name', 1)] if col_indices.get('name', -1) >= 0 else 'Unknown Product'
            image_url = selected_product[col_indices.get('image_url', 7)] if col_indices.get('image_url', -1) >= 0 else ''
            affiliate_link = selected_product[col_indices.get('affiliate_link', 8)] if col_indices.get('affiliate_link', -1) >= 0 else ''

            bot_logger.log_info(
                "AmazonPAAPIClient",
                f"Returning Google Sheets product data for keywords: {keywords} -> {name}"
            )

            return {
                "ASIN": product_id,
                "Title": name,
                "ImageURL": image_url,
                "AffiliateLink": affiliate_link
            }

        except Exception as e:
            bot_logger.log_error(
                "AmazonPAAPIClient",
                e,
                f"Error reading products from Google Sheets, using fallback for keywords: {keywords}"
            )
            return self._get_fallback_mock_data(keywords, min_rating)

    def _get_fallback_mock_data(self, keywords: str, min_rating: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Fallback mock data when Google Sheets is unavailable.
        """
        import random
        import hashlib

        seed = hashlib.md5(keywords.encode()).hexdigest()
        random.seed(seed)

        mock_products = [
            {
                "name": f"Premium {keywords.title()} Professional",
                "image_url": f"https://picsum.photos/400/400?random={random.randint(1, 1000)}",
                "affiliate_link": f"https://www.amazon.it/dp/mock{random.randint(100000, 999999)}?tag={self.associate_tag}"
            }
        ]

        product = random.choice(mock_products)

        return {
            "ASIN": f"MOCK{random.randint(100000, 999999)}",
            "Title": product["name"],
            "ImageURL": product["image_url"],
            "AffiliateLink": product["affiliate_link"]
        }

# Глобальный экземпляр клиента
amazon_paapi_client = AmazonPAAPIClient()
