# services/amazon_paapi_client.py
import asyncio
from typing import Dict, Any, Optional, List
from config import conf
from services.logger import bot_logger

try:
    # Correct imports for python-amazon-paapi library
    from amazon_paapi.sdk.api.default_api import DefaultApi
    from amazon_paapi.sdk.models.partner_type import PartnerType
    from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest
    from amazon_paapi.sdk.models.search_items_resource import SearchItemsResource
    from amazon_paapi.sdk.models.get_items_request import GetItemsRequest
    from amazon_paapi.sdk.models.get_items_resource import GetItemsResource
    from amazon_paapi.sdk.models.delivery_flag import DeliveryFlag
    from amazon_paapi.sdk.rest import ApiException
    PAAPI_AVAILABLE = "python_amazon_paapi"
except ImportError as e:
    print(f"python-amazon-paapi import failed: {e}")
    PAAPI_AVAILABLE = False
    bot_logger.log_error("AmazonPAAPIClient", Exception("python-amazon-paapi SDK not available"), "Using fallback methods")


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
                if PAAPI_AVAILABLE == "python_amazon_paapi":
                    # Use python-amazon-paapi library with correct initialization
                    print(f"DEBUG: Initializing DefaultApi with access_key={self.access_key[:10]}..., host={self.host}, region={self.region}")
                    self.api_client = DefaultApi(
                        access_key=self.access_key,
                        secret_key=self.secret_key,
                        host=self.host,
                        region=self.region
                    )
                    print("DEBUG: DefaultApi initialized successfully")
                else:
                    # Fallback for other SDKs (should not happen with our current setup)
                    self.api_client = None
                    print("DEBUG: Unsupported PAAPI SDK")

                if self.api_client:
                    bot_logger.log_info("AmazonPAAPIClient", "PAAPI 5.0 client initialized successfully")
                else:
                    bot_logger.log_error("AmazonPAAPIClient", Exception("Failed to initialize API client"), "Client is None")

            except Exception as e:
                print(f"DEBUG: Failed to initialize PAAPI client: {e}")
                import traceback
                traceback.print_exc()
                bot_logger.log_error("AmazonPAAPIClient", e, "Failed to initialize PAAPI client")
                self.api_client = None

    async def search_items(self, keywords: str, min_rating: float = 0.0, filters: Optional[Dict[str, Any]] = None, browse_node_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Advanced search for products using Amazon PA API 5.0 with sophisticated filtering.

        Args:
            keywords: Search keywords
            min_rating: Minimum rating filter
            filters: Advanced filters dictionary
            browse_node_ids: List of browse node IDs to search within

        Returns:
            Product data dictionary or None if error
        """
        # If Amazon API is disabled or SDK not available, use fallback
        if not self.use_amazon_api or not PAAPI_AVAILABLE or not self.api_client:
            bot_logger.log_info("AmazonPAAPIClient", "Using Google Sheets fallback for product data")
            return self._get_sheets_fallback_data(keywords, min_rating, browse_node_ids)

        # Set default filters if none provided
        if filters is None:
            filters = {
                "MinPrice": 10.00,
                "MinSavingPercent": 5,
                "MinReviewsRating": max(min_rating, 3.5),
                "FulfilledByAmazon": True
            }

        try:
            if PAAPI_AVAILABLE == "python_amazon_paapi":
                # Use python-amazon-paapi with browse node search if available
                if browse_node_ids:
                    return self._browse_node_search_api(browse_node_ids, keywords, min_rating, filters)
                else:
                    return self._basic_search_api(keywords, min_rating)

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, f"Unexpected error for keywords: {keywords}")
            return self._get_sheets_fallback_data(keywords, min_rating, browse_node_ids)

    async def _advanced_search_api(self, keywords: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Advanced search using SearchItems + GetItems enrichment."""
        try:
            # Step 1: Search for candidate products
            candidate_products = self._search_candidates(keywords, filters)
            if not candidate_products:
                return self._get_sheets_fallback_data(keywords, filters.get("MinReviewsRating", 0))

            # Step 2: Extract ASINs and enrich with detailed data
            candidate_asins = [p.get('asin') for p in candidate_products if p.get('asin')]

            # Step 3: Get detailed information for top candidates
            enriched_products = self._enrich_products(candidate_asins)

            # Step 4: Apply final filtering and select best product
            final_product = self._select_best_product(enriched_products, filters)

            if final_product:
                bot_logger.log_info("AmazonPAAPIClient",
                                  f"Successfully retrieved premium product: {final_product.get('Title', 'Unknown')}")
                return final_product

            return self._get_sheets_fallback_data(keywords, filters.get("MinReviewsRating", 0))

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, f"Advanced search failed for keywords: {keywords}")
            return self._get_sheets_fallback_data(keywords, filters.get("MinReviewsRating", 0))

    def _search_candidates(self, keywords: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for candidate products using SearchItems API."""
        try:
            # Convert price to cents for API
            min_price_cents = int(filters.get("MinPrice", 0) * 100) if filters.get("MinPrice") else None

            # Handle delivery flags
            delivery_flags = []
            if filters.get("FulfilledByAmazon"):
                delivery_flags.append(DeliveryFlag.FULFILLEDBYAMAZON)

            # Create search request
            search_request = SearchItemsRequest(
                partner_tag=self.associate_tag,
                partner_type=PartnerType.ASSOCIATES,
                marketplace="www.amazon.it",
                keywords=keywords,
                search_index="All",
                item_page=1,
                item_count=10,
                sort_by="Featured",
                min_price=min_price_cents,
                min_saving_percent=filters.get("MinSavingPercent"),
                min_reviews_rating=filters.get("MinReviewsRating"),
                delivery_flags=delivery_flags if delivery_flags else None
            )

            response = self.api_client.search_items(search_request)

            if response and hasattr(response, 'search_result') and response.search_result:
                items = getattr(response.search_result, 'items', [])
                return [item.to_dict() if hasattr(item, 'to_dict') else item for item in items]

            return []

        except ApiException as e:
            bot_logger.log_error("AmazonPAAPIClient", Exception(f"Search API Error: {e.reason}"), f"Keywords: {keywords}")
            return []
        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, f"Search failed for keywords: {keywords}")
            return []

    def _enrich_products(self, asins: List[str]) -> List[Dict[str, Any]]:
        """Enrich products with detailed information using GetItems API."""
        if not asins:
            return []

        try:
            # Split ASINs into chunks of 10
            asin_chunks = [asins[i:i + 10] for i in range(0, len(asins), 10)]
            enriched_items = []

            for chunk in asin_chunks:
                get_request = GetItemsRequest(
                    partner_tag=self.associate_tag,
                    partner_type=PartnerType.ASSOCIATES,
                    marketplace="www.amazon.it",
                    item_ids=chunk,
                    resources=[
                        GetItemsResource.ITEMINFO_TITLE,
                        GetItemsResource.OFFERS_LISTINGS_PRICE,
                        GetItemsResource.IMAGES_PRIMARY_LARGE,
                        GetItemsResource.CUSTOMERREVIEWS_COUNT,
                        GetItemsResource.CUSTOMERREVIEWS_STARRATING,
                        GetItemsResource.ITEMINFO_FEATURES,
                        GetItemsResource.BROWSENODEINFO_WEBSITESALESRANK
                    ]
                )

                try:
                    response = self.api_client.get_items(get_request)
                    if response and hasattr(response, 'items_result') and response.items_result:
                        items = getattr(response.items_result, 'items', [])
                        enriched_items.extend([item.to_dict() if hasattr(item, 'to_dict') else item for item in items])
                except ApiException as e:
                    bot_logger.log_error("AmazonPAAPIClient", Exception(f"GetItems API Error: {e.reason}"), f"ASINs: {chunk}")
                except Exception as e:
                    bot_logger.log_error("AmazonPAAPIClient", e, f"GetItems failed for ASINs: {chunk}")

                # Rate limiting
                import asyncio
                asyncio.sleep(0.1)

            return enriched_items

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, f"Enrichment failed for ASINs: {asins}")
            return []

    def _select_best_product(self, products: List[Dict[str, Any]], filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select the best product based on filters and quality metrics."""
        if not products:
            return None

        min_reviews_count = filters.get("MinReviewsCount", 50)
        min_rating = filters.get("MinReviewsRating", 3.5)

        # Filter and score products
        scored_products = []
        for product in products:
            try:
                # Extract review data
                customer_reviews = product.get('customer_reviews', {})
                review_count = customer_reviews.get('count', 0) if customer_reviews else 0
                rating = float(customer_reviews.get('star_rating', {}).get('rating', 0)) if customer_reviews.get('star_rating') else 0

                # Apply filters
                if review_count < min_reviews_count or rating < min_rating:
                    continue

                # Calculate quality score (higher is better)
                # Sales rank (lower rank number = better selling)
                sales_rank = product.get('browse_node_info', {}).get('website_sales_rank', 999999)
                if isinstance(sales_rank, dict):
                    sales_rank = sales_rank.get('sales_rank', 999999)

                # Score = rating * log(review_count + 1) / log(sales_rank + 1)
                import math
                quality_score = rating * math.log(review_count + 1) / math.log(sales_rank + 1) if sales_rank > 0 else rating

                scored_products.append((quality_score, product))

            except Exception as e:
                continue

        if not scored_products:
            return None

        # Select product with highest quality score
        best_product = max(scored_products, key=lambda x: x[0])[1]

        # Convert to our standard format
        return self._convert_to_standard_format(best_product)

    def _convert_to_standard_format(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Convert enriched product data to our standard format."""
        # Basic Info
        title = product.get('item_info', {}).get('title', {}).get('display_value', 'N/A')
        price = product.get('offers', {}).get('listings', [{}])[0].get('price', {}).get('display_amount', 'N/A')
        reviews = product.get('customer_reviews', {}).get('count', 'N/A') if product.get('customer_reviews') else 'N/A'
        link = product.get('detail_page_url', 'N/A')
        image = product.get('images', {}).get('primary', {}).get('large', {}).get('url', 'N/A')

        # Enhanced data
        sales_rank = product.get('browse_node_info', {}).get('website_sales_rank', 'N/A')
        if isinstance(sales_rank, dict):
            sales_rank = sales_rank.get('sales_rank', 'N/A')

        rating = product.get('customer_reviews', {}).get('star_rating', {}).get('rating', 'N/A') if product.get('customer_reviews', {}).get('star_rating') else 'N/A'

        # Features as description
        features = product.get('item_info', {}).get('features', {}).get('display_values', [])
        description = ' '.join(features[:3]) if features else ''

        return {
            "ASIN": product.get('asin', ''),
            "Title": title,
            "ImageURL": image,
            "AffiliateLink": link,
            "Price": price,
            "Rating": str(rating),
            "ReviewsCount": str(reviews),
            "SalesRank": str(sales_rank),
            "Description": description
        }

    def _browse_node_search_api(self, browse_node_ids: List[str], keywords: str, min_rating: float, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Search within specific browse nodes using Amazon PA API."""
        try:
            # Try each browse node until we find products
            for node_id in browse_node_ids:
                try:
                    search_items_request = SearchItemsRequest(
                        partner_tag=self.associate_tag,
                        partner_type=PartnerType.ASSOCIATES,
                        marketplace="www.amazon.it",
                        browse_node_id=node_id,
                        keywords=keywords if keywords else None,
                        search_index="All",
                        item_count=5,
                        min_reviews_rating=max(min_rating, 3.5),
                        resources=[
                            SearchItemsResource.ITEMINFO_TITLE,
                            SearchItemsResource.OFFERS_LISTINGS_PRICE,
                            SearchItemsResource.IMAGES_PRIMARY_LARGE,
                            SearchItemsResource.ITEMINFO_FEATURES,
                            SearchItemsResource.ITEMINFO_PRODUCTINFO,
                        ],
                    )

                    # Apply additional filters
                    if filters.get("MinPrice"):
                        search_items_request.min_price = int(filters["MinPrice"] * 100)  # Convert to cents
                    if filters.get("MinSavingPercent"):
                        search_items_request.min_saving_percent = filters["MinSavingPercent"]

                    response = self.api_client.search_items(search_items_request)

                    if response.search_result and response.search_result.items:
                        item = response.search_result.items[0]
                        product_data = self._extract_product_data(item)
                        bot_logger.log_info("AmazonPAAPIClient",
                                          f"Found product in browse node {node_id}: {product_data.get('Title', 'Unknown')}")
                        return product_data

                    # Rate limiting between node searches
                    import asyncio
                    asyncio.sleep(0.2)

                except ApiException as e:
                    bot_logger.log_error("AmazonPAAPIClient",
                                       Exception(f"Browse node search API Error: {e.reason}"),
                                       f"Node ID: {node_id}, Keywords: {keywords}")
                    continue
                except Exception as e:
                    bot_logger.log_error("AmazonPAAPIClient", e,
                                       f"Browse node search failed for node {node_id}, keywords: {keywords}")
                    continue

            # No products found in any browse node
            bot_logger.log_info("AmazonPAAPIClient",
                              f"No products found in browse nodes {browse_node_ids} for keywords: {keywords}")
            return None

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e,
                               f"Browse node search failed for nodes {browse_node_ids}, keywords: {keywords}")
            return None

    def _basic_search_api(self, keywords: str, min_rating: float) -> Optional[Dict[str, Any]]:
        """Fallback to basic search for paapi5_python_sdk."""
        try:
            search_items_request = SearchItemsRequest(
                partner_tag=self.associate_tag,
                partner_type=PartnerType.ASSOCIATES,
                keywords=keywords,
                search_index="All",
                item_count=5,
                resources=[
                    SearchItemsResource.ITEMINFO_TITLE,
                    SearchItemsResource.OFFERS_LISTINGS_PRICE,
                    SearchItemsResource.IMAGES_PRIMARY_LARGE,
                    SearchItemsResource.ITEMINFO_FEATURES,
                    SearchItemsResource.ITEMINFO_PRODUCTINFO,
                ],
            )

            if min_rating > 0:
                search_items_request.min_reviews_rating = min_rating

            response = self.api_client.search_items(search_items_request)

            if response.search_result and response.search_result.items:
                item = response.search_result.items[0]
                return self._extract_product_data(item)

            return None

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, f"Basic search failed for keywords: {keywords}")
            return None

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
