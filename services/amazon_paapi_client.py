# services/amazon_paapi_client.py
import asyncio
from typing import Dict, Any, Optional
from config import conf
from services.logger import bot_logger

try:
    from amazon.paapi import AmazonAPI
    PAAPI_AVAILABLE = "amazon_paapi"
    print("DEBUG: amazon.paapi imported successfully")
except ImportError as e:
    print(f"DEBUG: amazon.paapi import failed: {e}")
    try:
        from paapi5_python_sdk.api.default_api import DefaultApi
        from paapi5_python_sdk.models.partner_type import PartnerType
        from paapi5_python_sdk.models.search_items_request import SearchItemsRequest
        from paapi5_python_sdk.models.search_items_resource import SearchItemsResource
        from paapi5_python_sdk.rest import ApiException
        PAAPI_AVAILABLE = "paapi5_python_sdk"
        print("DEBUG: paapi5_python_sdk imported successfully")
    except ImportError as e2:
        print(f"DEBUG: paapi5_python_sdk import failed: {e2}")
        PAAPI_AVAILABLE = False
        bot_logger.log_error("AmazonPAAPIClient", Exception("PAAPI5 SDK not available"), "Using fallback methods")


class AmazonPAAPIClient:
    """Amazon Product Advertising API 5.0 client with PAAPI5 SDK."""

    def __init__(self):
        self.access_key = conf.amazon.access_key
        self.secret_key = conf.amazon.secret_key
        self.associate_tag = conf.amazon.associate_tag
        self.region = conf.amazon.region
        self.marketplace = conf.amazon.marketplace
        self.host = "webservices.amazon.it"  # Host for Italy

        # Check if Amazon API is enabled
        self.use_amazon_api = getattr(conf.amazon, 'use_api', True)
        if isinstance(self.use_amazon_api, str):
            self.use_amazon_api = self.use_amazon_api.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(self.use_amazon_api, bool):
            self.use_amazon_api = self.use_amazon_api
        else:
            self.use_amazon_api = False  # Default to False for safety

        # Initialize API client if SDK is available
        self.api_client = None
        if PAAPI_AVAILABLE and self.use_amazon_api:
            try:
                if PAAPI_AVAILABLE == "amazon_paapi":
                    # Use amazon.paapi package
                    print(f"DEBUG: Initializing AmazonAPI with access_key={self.access_key[:10]}..., partner_tag={self.associate_tag}")
                    self.api_client = AmazonAPI(
                        access_key=self.access_key,
                        secret_key=self.secret_key,
                        partner_tag=self.associate_tag,
                        country='IT'  # Italy
                    )
                    print("DEBUG: AmazonAPI initialized successfully")
                else:
                    # Use paapi5_python_sdk
                    self.api_client = DefaultApi(
                        access_key=self.access_key,
                        secret_key=self.secret_key,
                        host=self.host,
                        region=self.region
                    )
                bot_logger.log_info("AmazonPAAPIClient", "PAAPI 5.0 client initialized successfully")
            except Exception as e:
                print(f"DEBUG: Failed to initialize PAAPI client: {e}")
                import traceback
                traceback.print_exc()
                bot_logger.log_error("AmazonPAAPIClient", e, "Failed to initialize PAAPI client")
                self.api_client = None

    async def search_items(self, keywords: str, min_rating: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Search for products using Amazon PA API 5.0.

        Args:
            keywords: Search keywords
            min_rating: Minimum rating filter

        Returns:
            Product data dictionary or None if error
        """
        # If Amazon API is disabled or SDK not available, use fallback
        if not self.use_amazon_api or not PAAPI_AVAILABLE or not self.api_client:
            bot_logger.log_info("AmazonPAAPIClient", "Using Google Sheets fallback for product data")
            return self._get_sheets_fallback_data(keywords, min_rating)

        try:
            if PAAPI_AVAILABLE == "amazon_paapi":
                # Use amazon.paapi package
                response = self.api_client.search_items(keywords=keywords, search_index='All')

                if response and hasattr(response, 'data') and response.data:
                    # Extract first item from amazon.paapi response
                    item = response.data[0]

                    # Convert amazon.paapi format to our standard format
                    product_data = {
                        "ASIN": getattr(item, 'asin', ''),
                        "Title": getattr(item, 'product_title', ''),
                        "ImageURL": getattr(item, 'product_photo', ''),
                        "AffiliateLink": getattr(item, 'product_url', ''),
                        "Price": getattr(item, 'product_price', ''),
                        "Rating": str(getattr(item, 'product_star_rating', '')),
                        "ReviewsCount": str(getattr(item, 'product_num_ratings', '')),
                        "Category": getattr(item, 'product_byline', ''),
                        "Description": getattr(item, 'product_description', '')
                    }

                    bot_logger.log_info("AmazonPAAPIClient",
                                      f"Successfully retrieved product: {product_data.get('Title', 'Unknown')}")

                    return product_data
                else:
                    bot_logger.log_error("AmazonPAAPIClient", Exception("No items found"), f"Keywords: {keywords}")
                    return self._get_sheets_fallback_data(keywords, min_rating)

            else:
                # Use paapi5_python_sdk
                # Create search request
                search_items_request = SearchItemsRequest(
                    partner_tag=self.associate_tag,
                    partner_type=PartnerType.ASSOCIATES,
                    keywords=keywords,
                    search_index="All",
                    item_count=5,  # Get multiple items for selection
                    resources=[
                        SearchItemsResource.ITEMINFO_TITLE,
                        SearchItemsResource.OFFERS_LISTINGS_PRICE,
                        SearchItemsResource.IMAGES_PRIMARY_LARGE,
                        SearchItemsResource.ITEMINFO_FEATURES,
                        SearchItemsResource.ITEMINFO_PRODUCT_INFO,
                        SearchItemsResource.OFFERS_SUMMARIES_HIGHEST_PRICE,
                        SearchItemsResource.OFFERS_SUMMARIES_LOWEST_PRICE,
                        SearchItemsResource.ITEMINFO_BY_LINE_INFO,
                        SearchItemsResource.ITEMINFO_MANUFACTURE_INFO,
                    ],
                )

                # Add rating filter if specified
                if min_rating > 0:
                    search_items_request.min_reviews_rating = min_rating

                # Perform search
                response = self.api_client.search_items(search_items_request)

                if response.search_result and response.search_result.items:
                    # Get the first item
                    item = response.search_result.items[0]

                    # Extract product data
                    product_data = self._extract_product_data(item)

                    bot_logger.log_info("AmazonPAAPIClient",
                                      f"Successfully retrieved product: {product_data.get('Title', 'Unknown')}")

                    return product_data
                else:
                    bot_logger.log_error("AmazonPAAPIClient", Exception("No items found"), f"Keywords: {keywords}")
                    return self._get_sheets_fallback_data(keywords, min_rating)

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, f"Unexpected error for keywords: {keywords}")
            return self._get_sheets_fallback_data(keywords, min_rating)

    def _extract_product_data(self, item) -> Dict[str, Any]:
        """Extract product data from PAAPI response item."""
        product_data = {
            "ASIN": getattr(item, 'asin', ''),
            "Title": "",
            "ImageURL": "",
            "AffiliateLink": getattr(item, 'detail_page_url', ''),
            "Price": "",
            "Rating": "",
            "ReviewsCount": "",
            "Category": "",
            "Description": ""
        }

        # Extract title
        if hasattr(item, 'item_info') and item.item_info:
            if hasattr(item.item_info, 'title') and item.item_info.title:
                product_data["Title"] = getattr(item.item_info.title, 'display_value', '')

            # Extract category
            if hasattr(item.item_info, 'product_info') and item.item_info.product_info:
                if hasattr(item.item_info.product_info, 'item_dimensions') and item.item_info.product_info.item_dimensions:
                    if hasattr(item.item_info.product_info.item_dimensions, 'item_width') and item.item_info.product_info.item_dimensions.item_width:
                        product_data["Category"] = getattr(item.item_info.product_info.item_dimensions.item_width, 'display_value', '')

        # Extract image
        if hasattr(item, 'images') and item.images:
            if hasattr(item.images, 'primary') and item.images.primary:
                if hasattr(item.images.primary, 'large') and item.images.primary.large:
                    product_data["ImageURL"] = getattr(item.images.primary.large, 'url', '')

        # Extract price
        if hasattr(item, 'offers') and item.offers:
            if hasattr(item.offers, 'listings') and item.offers.listings:
                for listing in item.offers.listings:
                    if hasattr(listing, 'price') and listing.price:
                        product_data["Price"] = getattr(listing.price, 'display_amount', '')
                        break

        # Extract rating and reviews
        if hasattr(item, 'item_info') and item.item_info:
            if hasattr(item.item_info, 'product_info') and item.item_info.product_info:
                if hasattr(item.item_info.product_info, 'customer_reviews') and item.item_info.product_info.customer_reviews:
                    reviews = item.item_info.product_info.customer_reviews
                    if hasattr(reviews, 'count') and reviews.count:
                        product_data["ReviewsCount"] = str(reviews.count)
                    if hasattr(reviews, 'star_rating') and reviews.star_rating:
                        if hasattr(reviews.star_rating, 'rating') and reviews.star_rating.rating:
                            product_data["Rating"] = str(reviews.star_rating.rating)

        # Extract description/features
        if hasattr(item, 'item_info') and item.item_info:
            if hasattr(item.item_info, 'features') and item.item_info.features:
                if hasattr(item.item_info.features, 'display_values') and item.item_info.features.display_values:
                    product_data["Description"] = ' '.join(item.item_info.features.display_values[:3])  # First 3 features

        return product_data

    def _get_sheets_fallback_data(self, keywords: str, min_rating: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Get product data from Google Sheets as fallback when Amazon API is unavailable.

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
                    "Using basic fallback"
                )
                return self._get_basic_fallback_data(keywords)

            # Parse headers
            headers = products_data[0]
            if len(headers) < 11:
                bot_logger.log_error(
                    "AmazonPAAPIClient",
                    Exception("Invalid products worksheet format"),
                    "Using basic fallback"
                )
                return self._get_basic_fallback_data(keywords)

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
                return self._get_basic_fallback_data(keywords)

            # Select a random matching product
            import random
            selected_product = random.choice(matching_products)

            # Extract product data
            product_id = selected_product[col_indices.get('id', 0)] if col_indices.get('id', -1) >= 0 else 'UNKNOWN'
            name = selected_product[col_indices.get('name', 1)] if col_indices.get('name', -1) >= 0 else 'Unknown Product'
            image_url = selected_product[col_indices.get('image_url', 7)] if col_indices.get('image_url', -1) >= 0 else ''
            affiliate_link = selected_product[col_indices.get('affiliate_link', 8)] if col_indices.get('affiliate_link', -1) >= 0 else ''
            price = selected_product[col_indices.get('price', 4)] if col_indices.get('price', -1) >= 0 else ''
            rating = selected_product[col_indices.get('rating', 5)] if col_indices.get('rating', -1) >= 0 else ''
            reviews_count = selected_product[col_indices.get('reviews_count', 6)] if col_indices.get('reviews_count', -1) >= 0 else ''

            bot_logger.log_info(
                "AmazonPAAPIClient",
                f"Using Google Sheets fallback for keywords: {keywords} -> {name}"
            )

            return {
                "ASIN": product_id,
                "Title": name,
                "ImageURL": image_url,
                "AffiliateLink": affiliate_link,
                "Price": price,
                "Rating": rating,
                "ReviewsCount": reviews_count
            }

        except Exception as e:
            bot_logger.log_error(
                "AmazonPAAPIClient",
                e,
                f"Google Sheets fallback failed for keywords: {keywords}"
            )
            return self._get_basic_fallback_data(keywords)

    def _get_basic_fallback_data(self, keywords: str) -> Dict[str, Any]:
        """Basic fallback when both Amazon API and Google Sheets fail."""
        import random
        import hashlib

        seed = hashlib.md5(keywords.encode()).hexdigest()
        random.seed(seed)

        return {
            "ASIN": f"FALLBACK{random.randint(100000, 999999)}",
            "Title": f"Premium {keywords.title()} Product",
            "ImageURL": f"https://picsum.photos/400/400?random={random.randint(1, 1000)}",
            "AffiliateLink": f"https://www.amazon.it/dp/fallback{random.randint(100000, 999999)}?tag={self.associate_tag}",
            "Price": f"€{random.randint(10, 100)},{random.randint(10, 99)}",
            "Rating": f"{random.uniform(3.5, 5.0):.1f}",
            "ReviewsCount": str(random.randint(10, 1000))
        }

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
