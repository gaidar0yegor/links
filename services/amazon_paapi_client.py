# services/amazon_paapi_client.py
import asyncio
import time
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import conf
from services.logger import bot_logger


# Global session for connection reuse (thread-safe)
_http_session: Optional[requests.Session] = None


def _get_http_session() -> requests.Session:
    """Get or create a reusable HTTP session with retry logic."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # 3 retries
            backoff_factor=1,  # 1s, 2s, 4s delays
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["POST"],  # Retry POST requests
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
        )
        _http_session.mount("https://", adapter)
        
    return _http_session


def _sign_aws4_request(host: str, region: str, access_key: str, secret_key: str, 
                        payload: str, service: str = "ProductAdvertisingAPI") -> Dict[str, str]:
    """
    Create AWS Signature Version 4 headers for PA-API requests.
    Used for raw HTTP calls to bypass SDK limitations (e.g., OffersV2).
    """
    method = "POST"
    uri = "/paapi5/getitems"
    
    # Use timezone-aware UTC datetime (Python 3.12+ compatible)
    t = datetime.now(timezone.utc)
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    # Headers
    headers = {
        'content-encoding': 'amz-1.0',
        'content-type': 'application/json; charset=utf-8',
        'host': host,
        'x-amz-date': amz_date,
        'x-amz-target': 'com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems'
    }
    
    # Canonical request
    signed_headers = ';'.join(sorted(headers.keys()))
    canonical_headers = ''.join([f"{k}:{v}\n" for k, v in sorted(headers.items())])
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    canonical_request = f"{method}\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    
    # String to sign
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    
    # Signing key
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
    
    k_date = sign(('AWS4' + secret_key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, 'aws4_request')
    
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    # Authorization header
    authorization = f"{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    headers['Authorization'] = authorization
    
    return headers

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

    def _get_items_raw_v2(self, asins: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch items using raw HTTP with OffersV2 resources.
        Bypasses SDK limitation that doesn't support OffersV2 enums.
        
        Args:
            asins: List of ASINs to fetch (max 10 per request)
            
        Returns:
            List of item dictionaries with OffersV2 data
        """
        if not asins:
            return []
        
        # OffersV2 resources (validated as working)
        offersv2_resources = [
            "OffersV2.Listings.Price",
            "OffersV2.Listings.Availability",
            "OffersV2.Listings.Condition",
            "OffersV2.Listings.IsBuyBoxWinner",
            "OffersV2.Listings.MerchantInfo",
        ]
        
        # Other useful resources
        other_resources = [
            "ItemInfo.Title",
            "ItemInfo.Features",
            "Images.Primary.Large",
            "Images.Variants.Large",
            "BrowseNodeInfo.WebsiteSalesRank",
            "CustomerReviews.Count",
            "CustomerReviews.StarRating",
        ]
        
        payload = {
            "ItemIds": asins[:10],  # API limit is 10
            "PartnerTag": self.associate_tag,
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.it",
            "Resources": other_resources + offersv2_resources
        }
        
        payload_json = json.dumps(payload)
        
        try:
            headers = _sign_aws4_request(
                host=self.host,
                region=self.region,
                access_key=self.access_key,
                secret_key=self.secret_key,
                payload=payload_json
            )
            
            url = f"https://{self.host}/paapi5/getitems"
            
            # Use session for connection reuse and automatic retries
            session = _get_http_session()
            response = session.post(url, headers=headers, data=payload_json, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if "ItemsResult" in data and "Items" in data["ItemsResult"]:
                    items = data["ItemsResult"]["Items"]
                    
                    # Log each item's OffersV2 data
                    for item in items:
                        asin = item.get("ASIN", "?")
                        title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "")[:50]
                        
                        # Extract V2 price data
                        offers_v2 = item.get("OffersV2", {})
                        listings = offers_v2.get("Listings", [])
                        if listings:
                            listing = listings[0]
                            price = listing.get("Price", {}).get("Money", {}).get("DisplayAmount", "N/A")
                            is_buybox = "✓" if listing.get("IsBuyBoxWinner") else "✗"
                            merchant = listing.get("MerchantInfo", {}).get("Name", "?")
                            print(f"📦 API V2: {asin} | {price} | BuyBox:{is_buybox} | {merchant} | {title}...")
                        else:
                            print(f"📦 API V2: {asin} | No OffersV2 listings | {title}...")
                    
                    bot_logger.log_info("AmazonPAAPIClient", 
                        f"OffersV2 API success: {len(items)} items retrieved")
                    return items
                return []
            else:
                # Parse API error response
                error_msg = "Unknown error"
                try:
                    error_data = response.json()
                    if "Errors" in error_data and error_data["Errors"]:
                        error_msg = error_data["Errors"][0].get("Message", error_msg)
                except:
                    error_msg = response.text[:200]
                
                bot_logger.log_error("AmazonPAAPIClient", 
                    Exception(f"OffersV2 API {response.status_code}"), error_msg)
                return []
                
        except requests.exceptions.Timeout:
            bot_logger.log_error("AmazonPAAPIClient", 
                Exception("OffersV2 API timeout"), f"ASINs: {asins[:3]}")
            return []
        except requests.exceptions.RequestException as e:
            bot_logger.log_error("AmazonPAAPIClient", e, "OffersV2 network error")
            return []
        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e, "OffersV2 unexpected error")
            return []

    async def search_items(self, keywords: str, min_rating: float = 0.0, filters: Optional[Dict[str, Any]] = None, browse_node_ids: Optional[List[str]] = None, exclude_asins: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Advanced search for products using Amazon PA API 5.0 with sophisticated filtering.
        Now includes deduplication by excluding already posted ASINs.

        Args:
            keywords: Search keywords
            min_rating: Minimum rating filter
            filters: Advanced filters dictionary
            browse_node_ids: List of browse node IDs to search within
            exclude_asins: List of ASINs to exclude from results

        Returns:
            Product data dictionary or None if error
        """
        print(f"DEBUG: search_items called with keywords={keywords}, min_rating={min_rating}, browse_node_ids={browse_node_ids}, exclude_asins={len(exclude_asins) if exclude_asins else 0}")

        # If Amazon API is disabled or SDK not available, use fallback
        if not self.use_amazon_api or not PAAPI_AVAILABLE or not self.api_client:
            bot_logger.log_info("AmazonPAAPIClient", "Using Google Sheets fallback for product data")
            return self._get_sheets_fallback_data(keywords, min_rating, browse_node_ids)

        # Set default filters and merge with provided ones
        # Convert min_rating to integer for Amazon API (expects 1-5)
        min_rating_int = int(float(min_rating)) if min_rating else 3
        min_rating_int = max(1, min(min_rating_int, 5))  # Ensure within 1-5 range

        final_filters = {
            "MinPrice": 10.00,
            "MinSavingPercent": 5,
            "MinReviewsRating": min_rating_int,
            "FulfilledByAmazon": True
        }
        if filters:
            # Filters passed from the campaign will override defaults.
            # `None` values mean the filter should be skipped.
            for key, value in filters.items():
                if value is not None:
                    final_filters[key] = value
                elif key in final_filters:
                    del final_filters[key]

        try:
            if PAAPI_AVAILABLE == "paapi5_python_sdk":
                # Use paapi5_python_sdk with advanced search
                return await self._advanced_search_api(keywords, final_filters, exclude_asins)
            elif PAAPI_AVAILABLE == "python_amazon_paapi":
                # Use python-amazon-paapi with browse node search if available
                print(f"DEBUG: search_items - browse_node_ids={browse_node_ids}, type={type(browse_node_ids)}")
                if browse_node_ids:
                    print(f"DEBUG: Calling browse_node_search_api with browse_node_ids={browse_node_ids}")
                    return self._browse_node_search_api(browse_node_ids, keywords, min_rating, final_filters, exclude_asins)
                else:
                    print(f"DEBUG: Calling basic_search_api")
                    return self._basic_search_api(keywords, min_rating, exclude_asins)

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
                        GetItemsResource.IMAGES_VARIANTS_LARGE,
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
                time.sleep(0.1)

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
        """
        Convert enriched product data to our standard format.
        Supports both V1 (snake_case SDK dict) and V2 (PascalCase raw dict) formats.
        """
        # Detect if V2 format (PascalCase keys like 'ItemInfo', 'OffersV2')
        is_v2 = 'ItemInfo' in product or 'OffersV2' in product
        
        if is_v2:
            # V2 format (raw API response)
            item_info = product.get('ItemInfo', {})
            title = item_info.get('Title', {}).get('DisplayValue', 'N/A')
            
            # Price from OffersV2
            price = 'N/A'
            offers_v2 = product.get('OffersV2', {})
            listings = offers_v2.get('Listings', [])
            if listings:
                money = listings[0].get('Price', {}).get('Money', {})
                price = money.get('DisplayAmount', 'N/A')
            
            # Fallback to V1 Offers if OffersV2 not present
            if price == 'N/A':
                offers_v1 = product.get('Offers', {})
                listings_v1 = offers_v1.get('Listings', [])
                if listings_v1:
                    price = listings_v1[0].get('Price', {}).get('DisplayAmount', 'N/A')
            
            reviews = product.get('CustomerReviews', {}).get('Count', 'N/A')
            link = product.get('DetailPageURL', 'N/A')
            image = product.get('Images', {}).get('Primary', {}).get('Large', {}).get('URL', 'N/A')
            
            sales_rank = product.get('BrowseNodeInfo', {}).get('WebsiteSalesRank', {})
            if isinstance(sales_rank, dict):
                sales_rank = sales_rank.get('SalesRank', 'N/A')
            
            star_rating = product.get('CustomerReviews', {}).get('StarRating', {})
            rating = star_rating.get('Value', 'N/A') if star_rating else 'N/A'
            
            features = item_info.get('Features', {}).get('DisplayValues', [])
            description = ' '.join(features[:3]) if features else ''
            
            asin = product.get('ASIN', '')
        else:
            # V1 format (SDK dict with snake_case)
            title = product.get('item_info', {}).get('title', {}).get('display_value', 'N/A')
            price = product.get('offers', {}).get('listings', [{}])[0].get('price', {}).get('display_amount', 'N/A')
            reviews = product.get('customer_reviews', {}).get('count', 'N/A') if product.get('customer_reviews') else 'N/A'
            link = product.get('detail_page_url', 'N/A')
            image = product.get('images', {}).get('primary', {}).get('large', {}).get('url', 'N/A')

            sales_rank = product.get('browse_node_info', {}).get('website_sales_rank', 'N/A')
            if isinstance(sales_rank, dict):
                sales_rank = sales_rank.get('sales_rank', 'N/A')

            rating = product.get('customer_reviews', {}).get('star_rating', {}).get('rating', 'N/A') if product.get('customer_reviews', {}).get('star_rating') else 'N/A'

            features = product.get('item_info', {}).get('features', {}).get('display_values', [])
            description = ' '.join(features[:3]) if features else ''
            
            asin = product.get('asin', '')

        return {
            "ASIN": asin,
            "Title": title,
            "ImageURL": image,
            "AffiliateLink": link,
            "Price": price,
            "Rating": str(rating),
            "ReviewsCount": str(reviews),
            "SalesRank": str(sales_rank),
            "Description": description
        }

    def _browse_node_search_api(self, browse_node_ids: List[str], keywords: str, min_rating: float, filters: Dict[str, Any], exclude_asins: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Search within specific browse nodes using Amazon PA API with deduplication."""
        try:
            # Convert min_rating to integer for Amazon API
            min_rating_int = int(float(min_rating)) if min_rating else 3
            min_rating_int = max(1, min(min_rating_int, 5))  # Ensure within 1-5 range
            print(f"DEBUG: browse_node_search_api - min_rating={min_rating}, min_rating_int={min_rating_int}, exclude_asins={len(exclude_asins) if exclude_asins else 0}")

            # Try each browse node until we find products
            for node_id in browse_node_ids:
                try:
                    # Randomize page to get fresh results
                    import random
                    page_num = random.randint(1, 5)

                    # Increase item_count to get more variety and filter out excluded ASINs
                    search_items_request = SearchItemsRequest(
                        partner_tag=self.associate_tag,
                        partner_type=PartnerType.ASSOCIATES,
                        marketplace="www.amazon.it",
                        browse_node_id=node_id,
                        keywords=keywords if keywords else None,
                        search_index="All",
                        item_page=page_num,
                        item_count=10,  # Get more results for variety
                        min_reviews_rating=min_rating_int,
                        # Add price filter to ensure we get products with prices
                        min_price=500,  # Minimum 5 EUR to filter out free/low-value items
                        resources=[
                            SearchItemsResource.ITEMINFO_TITLE,
                            SearchItemsResource.OFFERS_LISTINGS_PRICE,
                            SearchItemsResource.IMAGES_PRIMARY_LARGE,
                            SearchItemsResource.IMAGES_VARIANTS_LARGE, # Request variant images
                            SearchItemsResource.ITEMINFO_FEATURES,
                            SearchItemsResource.ITEMINFO_PRODUCTINFO,
                            SearchItemsResource.CUSTOMERREVIEWS_COUNT,
                            SearchItemsResource.CUSTOMERREVIEWS_STARRATING,
                        ],
                    )

                    # Apply additional filters
                    if filters.get("MinPrice"):
                        search_items_request.min_price = int(filters["MinPrice"] * 100)  # Convert to cents

                    response = self.api_client.search_items(search_items_request)

                    if response.search_result and response.search_result.items:
                        # Filter out excluded ASINs and find the first valid product
                        for item in response.search_result.items:
                            item_asin = getattr(item, 'asin', '')
                            if exclude_asins and item_asin in exclude_asins:
                                print(f"DEBUG: Skipping already posted ASIN: {item_asin}")
                                continue

                            product_data = self._extract_product_data(item)
                            if product_data and product_data.get('ASIN'):
                                bot_logger.log_info("AmazonPAAPIClient",
                                                  f"Found new product in browse node {node_id}: {product_data.get('Title', 'Unknown')} (ASIN: {product_data.get('ASIN')})")
                                return product_data

                    # Rate limiting between node searches
                    time.sleep(0.8)

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
                              f"No new products found in browse nodes {browse_node_ids} for keywords: {keywords} (excluded {len(exclude_asins) if exclude_asins else 0} ASINs)")
            return None

        except Exception as e:
            bot_logger.log_error("AmazonPAAPIClient", e,
                               f"Browse node search failed for nodes {browse_node_ids}, keywords: {keywords}")
            return None

    def _basic_search_api(self, keywords: str, min_rating: float) -> Optional[Dict[str, Any]]:
        """Fallback to basic search for paapi5_python_sdk."""
        try:
            # Convert min_rating to integer for Amazon API
            min_rating_int = int(float(min_rating)) if min_rating else 3
            min_rating_int = max(1, min(min_rating_int, 5))  # Ensure within 1-5 range

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
                    SearchItemsResource.IMAGES_VARIANTS_LARGE, # Request variant images
                    SearchItemsResource.ITEMINFO_FEATURES,
                    SearchItemsResource.ITEMINFO_PRODUCTINFO,
                    SearchItemsResource.CUSTOMERREVIEWS_COUNT,
                    SearchItemsResource.CUSTOMERREVIEWS_STARRATING,
                ],
            )

            if min_rating > 0:
                search_items_request.min_reviews_rating = min_rating_int

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
            "ImageURLs": [], # Changed from ImageURL to ImageURLs
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

        # Extract images (primary and variants)
        image_urls = []
        if hasattr(item, 'images') and item.images:
            # Primary image
            if hasattr(item.images, 'primary') and item.images.primary and hasattr(item.images.primary, 'large') and item.images.primary.large:
                primary_url = getattr(item.images.primary.large, 'url', '')
                if primary_url:
                    image_urls.append(primary_url)
            
            # Variant images
            if hasattr(item.images, 'variants') and item.images.variants:
                for variant in item.images.variants:
                    if len(image_urls) >= 3:
                        break
                    if hasattr(variant, 'large') and variant.large:
                        variant_url = getattr(variant, 'large', {}).get('url', '')
                        if variant_url and variant_url not in image_urls:
                            image_urls.append(variant_url)
        
        product_data["ImageURLs"] = image_urls[:3]
        product_data["image_urls"] = image_urls[:3]  # Also add lowercase for compatibility


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

    async def search_items_enhanced(self, browse_node_ids: List[str], min_rating: float = 0.0,
                                   min_price: Optional[float] = None,
                                   fulfilled_by_amazon: Optional[bool] = None, max_results: int = 10,
                                   max_sales_rank: Optional[int] = None,
                                   min_review_count: int = 0,
                                   items_per_node: int = 10) -> List[Dict[str, Any]]:
        """
        Enhanced search that returns multiple products with sales rank information.
        Uses GetItems API to enrich data with ratings, reviews, and sales rank.
        Used by the product discovery cycle to populate the product queue.

        Args:
            browse_node_ids: List of Amazon browse node IDs to search within
            min_rating: Minimum customer rating (0.0-5.0)
            min_price: Minimum price filter
            fulfilled_by_amazon: Whether to filter for FBA products
            max_results: Maximum number of products to return
            max_sales_rank: Maximum sales rank for filtering
            items_per_node: Target items to fetch per node (searches multiple pages if > 10)

        Returns:
            List of product dictionaries with enhanced data
        """
        print(f"DEBUG: search_items_enhanced called with {len(browse_node_ids)} nodes, {items_per_node} items/node")

        # If Amazon API is disabled or SDK not available, return empty list
        if not self.use_amazon_api or not PAAPI_AVAILABLE or not self.api_client:
            print("DEBUG: Amazon API not available, returning empty list")
            return []

        try:
            candidate_asins = []
            
            # Calculate pages needed per node (API limit is 10 items per page)
            pages_per_node = max(1, (items_per_node + 9) // 10)  # Ceiling division
            import random

            # Phase 1: Search for candidate products using SearchItems
            for node_id in browse_node_ids:
                node_asins = []
                
                # Search multiple pages if needed
                for page_offset in range(pages_per_node):
                    try:
                        # For multi-page searches, use sequential pages 1,2,3...
                        # For single-page, randomize for variety
                        if pages_per_node > 1:
                            page_num = page_offset + 1  # Sequential: 1, 2, 3
                        else:
                            page_num = random.randint(1, 5)  # Random for single page
                        
                        # Create search request
                        search_request = SearchItemsRequest(
                            partner_tag=self.associate_tag,
                            partner_type=PartnerType.ASSOCIATES,
                            marketplace="www.amazon.it",
                            browse_node_id=node_id,
                            search_index="All",
                            item_page=page_num,
                            item_count=10,  # Max per page
                            sort_by="Featured",
                            resources=[
                                SearchItemsResource.ITEMINFO_TITLE,
                                SearchItemsResource.OFFERS_LISTINGS_PRICE,
                                SearchItemsResource.IMAGES_PRIMARY_LARGE,
                            ],
                        )

                        # Apply basic filters
                        if min_price:
                            search_request.min_price = int(min_price * 100)  # Convert to cents

                        # Execute search
                        response = self.api_client.search_items(search_request)

                        if response and hasattr(response, 'search_result') and response.search_result:
                            items = getattr(response.search_result, 'items', None) or []
                            
                            if not items:
                                # No more results, stop searching this node
                                print(f"📭 Node {node_id} page {page_num}: no results, stopping")
                                break

                            for item in items:
                                asin = getattr(item, 'asin', '')
                                # Validate ASIN format (alphanumeric, typically starts with B0)
                                if asin and len(asin) == 10 and asin not in node_asins:
                                    node_asins.append(asin)
                        else:
                            # No response, stop searching this node
                            print(f"📭 Node {node_id} page {page_num}: no results, stopping")
                            break

                        # Rate limiting between requests
                        time.sleep(0.8)

                    except ApiException as e:
                        print(f"DEBUG: API Exception for node {node_id} page {page_num}: {e.reason}")
                        continue
                    except Exception as e:
                        print(f"DEBUG: Exception for node {node_id} page {page_num}: {e}")
                        continue
                
                print(f"📦 Node {node_id}: {len(node_asins)} ASINs from {pages_per_node} page(s)")
                candidate_asins.extend(node_asins)

            # Remove duplicates (process all candidates to maximize results)
            candidate_asins = list(set(candidate_asins))
            print(f"📊 Total unique ASINs: {len(candidate_asins)}")

            if not candidate_asins:
                print("DEBUG: No candidate ASINs found")
                return []

            # Phase 2: Enrich candidate products with detailed data using GetItems
            enriched_products = await self._enrich_products_batch(candidate_asins)

            # Phase 3: Filter and return products that meet criteria
            print(f"DEBUG: Starting final filtering for {len(enriched_products)} products...")
            filtered_products = []
            
            # Statistics counters
            stats = {
                "total": len(enriched_products),
                "accepted": 0,
                "skipped_rating": 0,
                "skipped_rank": 0,
                "skipped_other": 0
            }
            
            for product in enriched_products:
                asin = product.get('asin', 'N/A')

                # Apply rating filter
                rating = product.get('rating')
                if min_rating and (rating is None or rating < min_rating):
                    # print(f"DEBUG: Skipping product {asin} - rating '{rating}' is below minimum '{min_rating}'")
                    stats["skipped_rating"] += 1
                    continue

                # Apply sales rank filter with bypass logic
                sales_rank = product.get('sales_rank')
                review_count = product.get('review_count')
                
                bypass_rank_check = False
                # If sales rank is missing BUT review count is high enough (2x min required), accept it
                if sales_rank is None and min_review_count > 0 and review_count is not None:
                    if review_count >= (min_review_count * 2):
                        bypass_rank_check = True
                        print(f"DEBUG: Bypassing missing sales rank for {asin} (Reviews: {review_count} >= {min_review_count * 2})")

                if not bypass_rank_check and max_sales_rank and (sales_rank is None or sales_rank > max_sales_rank):
                    if sales_rank:
                        print(f"DEBUG: Skipping product {asin} - sales rank '{sales_rank}' is above maximum '{max_sales_rank}'")
                    else:
                        # Only log if not bypassed
                        pass 
                        # print(f"DEBUG: Skipping product {asin} - missing sales rank")
                    stats["skipped_rank"] += 1
                    continue

                filtered_products.append(product)
                stats["accepted"] += 1
                if len(filtered_products) >= max_results:
                    break
            
            # Log summary instead of individual skips
            print(f"DEBUG: Filtering Summary: Total={stats['total']}, Accepted={stats['accepted']}, "
                  f"Skipped[Rating]={stats['skipped_rating']}, Skipped[Rank]={stats['skipped_rank']}")

            print(f"DEBUG: Returning {len(filtered_products)} enriched and filtered products")
            return filtered_products

        except Exception as e:
            print(f"DEBUG: search_items_enhanced failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _enrich_products_batch(self, asins: List[str]) -> List[Dict[str, Any]]:
        """
        Enrich a batch of products with detailed data using GetItems API with OffersV2.
        Uses raw HTTP requests to bypass SDK limitation for OffersV2 support.
        Includes web scraping fallback for missing data.
        """
        if not asins:
            return []

        enriched_products = []

        # Process in batches of 10 (Amazon API limit)
        for i in range(0, len(asins), 10):
            batch_asins = asins[i:i+10]

            try:
                # Use raw HTTP with OffersV2 resources
                items = self._get_items_raw_v2(batch_asins)
                
                if items:
                    for item in items:
                        # item is now a dict (not SDK object) with OffersV2 structure
                        enriched_data = self._extract_enriched_product_data_v2(item)
                        if enriched_data:
                            # Check if we need web scraping fallback for missing data
                            needs_scraping = (
                                enriched_data.get('price') is None or
                                enriched_data.get('rating') is None or
                                enriched_data.get('review_count') is None or
                                enriched_data.get('sales_rank') is None
                            )

                            if needs_scraping:
                                try:
                                    from services.amazon_scraper import enrich_product_with_scraping
                                    enriched_data = await enrich_product_with_scraping(enriched_data)
                                except Exception as e:
                                    print(f"DEBUG: Web scraping fallback failed: {e}")

                            enriched_products.append(enriched_data)
                else:
                    # Raw V2 failed, try web scraping
                    raise Exception("Raw V2 API returned no items")

                # Rate limiting between batches
                await asyncio.sleep(0.8)

            except Exception as e:
                print(f"DEBUG: GetItems V2 failed for batch {batch_asins[:3]}...: {e}")
                # Fallback to web scraping for the entire batch
                try:
                    from services.amazon_scraper import get_amazon_scraper
                    scraper = await get_amazon_scraper()

                    for asin in batch_asins:
                        scraped_data = await scraper.scrape_product_data(asin)
                        if scraped_data:
                            # Convert scraped data to enriched format
                            default_image = f"https://m.media-amazon.com/images/I/{asin}._SL500_.jpg"
                            enriched_data = {
                                'asin': scraped_data['asin'],
                                'title': scraped_data.get('title'),
                                'price': scraped_data.get('price'),
                                'currency': scraped_data.get('currency', 'EUR'),
                                'rating': scraped_data.get('rating'),
                                'review_count': scraped_data.get('review_count'),
                                'sales_rank': scraped_data.get('sales_rank'),
                                'image_urls': [default_image],
                                'affiliate_link': f"https://www.amazon.it/dp/{asin}?tag={self.associate_tag}",
                                'features': scraped_data.get('features', []),
                                'description': scraped_data.get('description')
                            }
                            enriched_products.append(enriched_data)
                            print(f"DEBUG: Used web scraping for ASIN {asin}")
                except Exception as scrape_e:
                    print(f"DEBUG: Web scraping fallback also failed: {scrape_e}")
                continue

        return enriched_products

    def _extract_enriched_product_data(self, item) -> Optional[Dict[str, Any]]:
        """
        Extract enriched product data from GetItems API response.
        This has access to customer reviews and sales rank data.
        """
        try:
            asin = getattr(item, 'asin', '')
            if not asin:
                return None

            product_data = {
                'asin': asin,
                'title': '',
                'price': None,
                'currency': 'EUR',
                'rating': None,
                'review_count': None,
                'sales_rank': None,
                'image_urls': [],
                'affiliate_link': getattr(item, 'detail_page_url', ''),
                'features': [],
                'description': '',
            }

            # Extract title
            if hasattr(item, 'item_info') and item.item_info:
                if hasattr(item.item_info, 'title') and item.item_info.title:
                    product_data['title'] = getattr(item.item_info.title, 'display_value', '')

            # Extract features/description from API (no scraping needed)
            if hasattr(item, 'item_info') and item.item_info:
                if hasattr(item.item_info, 'features') and item.item_info.features:
                    if hasattr(item.item_info.features, 'display_values') and item.item_info.features.display_values:
                        features = item.item_info.features.display_values
                        product_data['features'] = features
                        # Use first 2-3 features as description
                        product_data['description'] = ' '.join(features[:3]) if features else ''
                        # print(f"DEBUG: Extracted {len(features)} features from API for ASIN {asin}")

            # Extract price and discount
            if hasattr(item, 'offers') and item.offers:
                if hasattr(item.offers, 'listings') and item.offers.listings:
                    for listing in item.offers.listings:
                        if hasattr(listing, 'price') and listing.price:
                            amount = getattr(listing.price, 'amount', None)
                            currency = getattr(listing.price, 'currency', 'EUR')
                            if amount is not None:
                                product_data['price'] = float(amount)
                                product_data['currency'] = currency
                        
                        # Assuming we only care about the first listing with a price
                        if product_data['price'] is not None:
                            break

            # Extract rating and review count (available in GetItems)
            if hasattr(item, 'customer_reviews') and item.customer_reviews:
                if hasattr(item.customer_reviews, 'count') and item.customer_reviews.count:
                    product_data['review_count'] = int(item.customer_reviews.count)
                if hasattr(item.customer_reviews, 'star_rating') and item.customer_reviews.star_rating:
                    if hasattr(item.customer_reviews.star_rating, 'rating') and item.customer_reviews.star_rating.rating:
                        product_data['rating'] = float(item.customer_reviews.star_rating.rating)

            # Extract sales rank (available in GetItems)
            if hasattr(item, 'browse_node_info') and item.browse_node_info:
                if hasattr(item.browse_node_info, 'website_sales_rank') and item.browse_node_info.website_sales_rank:
                    sales_rank_data = item.browse_node_info.website_sales_rank
                    if isinstance(sales_rank_data, dict):
                        product_data['sales_rank'] = sales_rank_data.get('sales_rank')
                    elif hasattr(sales_rank_data, 'sales_rank'):
                        product_data['sales_rank'] = sales_rank_data.sales_rank

            # --- Image Extraction ---
            image_urls = []
            if hasattr(item, 'images') and item.images:
                # Add primary image first
                if hasattr(item.images, 'primary') and item.images.primary and hasattr(item.images.primary, 'large') and item.images.primary.large:
                    primary_url = item.images.primary.large.url
                    if primary_url:
                        image_urls.append(primary_url)
                
                # Add variant images, up to the limit
                if hasattr(item.images, 'variants') and item.images.variants:
                    for variant in item.images.variants:
                        if len(image_urls) >= 3:
                            break
                        if hasattr(variant, 'large') and variant.large:
                            variant_url = variant.large.url
                            if variant_url and variant_url not in image_urls:
                                image_urls.append(variant_url)

            product_data['image_urls'] = image_urls[:3] # Ensure we don't exceed 3
            
            return product_data

        except Exception as e:
            print(f"DEBUG: Failed to extract enriched product data: {e}")
            return None

    def _extract_enriched_product_data_v2(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract enriched product data from raw OffersV2 API response (dict format).
        Handles the new OffersV2 JSON structure with Price.Money.Amount path.
        """
        try:
            asin = item.get('ASIN', '')
            if not asin:
                return None

            product_data = {
                'asin': asin,
                'title': '',
                'price': None,
                'currency': 'EUR',
                'rating': None,
                'review_count': None,
                'sales_rank': None,
                'image_urls': [],
                'affiliate_link': item.get('DetailPageURL', ''),
                'features': [],
                'description': '',
                'is_buy_box_winner': None,
                'merchant_name': None,
            }

            # Extract title
            item_info = item.get('ItemInfo', {})
            if item_info.get('Title'):
                product_data['title'] = item_info['Title'].get('DisplayValue', '')

            # Extract features/description
            if item_info.get('Features'):
                features = item_info['Features'].get('DisplayValues', [])
                product_data['features'] = features
                product_data['description'] = ' '.join(features[:3]) if features else ''

            # Extract price from OffersV2 (new V2 structure)
            offers_v2 = item.get('OffersV2', {})
            listings = offers_v2.get('Listings', [])
            if listings:
                listing = listings[0]
                
                # Buy Box Winner (V2 exclusive)
                product_data['is_buy_box_winner'] = listing.get('IsBuyBoxWinner')
                
                # Merchant Info (V2 exclusive)
                merchant_info = listing.get('MerchantInfo', {})
                product_data['merchant_name'] = merchant_info.get('Name')
                
                # Price (V2 structure: Price.Money.Amount)
                price_obj = listing.get('Price', {})
                money = price_obj.get('Money', {})
                if money.get('Amount') is not None:
                    product_data['price'] = float(money['Amount'])
                    product_data['currency'] = money.get('Currency', 'EUR')

            # Fallback to V1 Offers if V2 not present
            if product_data['price'] is None:
                offers_v1 = item.get('Offers', {})
                listings_v1 = offers_v1.get('Listings', [])
                if listings_v1:
                    price_obj = listings_v1[0].get('Price', {})
                    if price_obj.get('Amount') is not None:
                        product_data['price'] = float(price_obj['Amount'])
                        product_data['currency'] = price_obj.get('Currency', 'EUR')

            # Extract rating and review count
            customer_reviews = item.get('CustomerReviews', {})
            if customer_reviews.get('Count') is not None:
                product_data['review_count'] = int(customer_reviews['Count'])
            if customer_reviews.get('StarRating'):
                star_rating = customer_reviews['StarRating']
                if star_rating.get('Value') is not None:
                    product_data['rating'] = float(star_rating['Value'])

            # Extract sales rank
            browse_node_info = item.get('BrowseNodeInfo', {})
            website_sales_rank = browse_node_info.get('WebsiteSalesRank', {})
            if isinstance(website_sales_rank, dict):
                product_data['sales_rank'] = website_sales_rank.get('SalesRank')

            # Extract images
            image_urls = []
            images = item.get('Images', {})
            
            # Primary image
            primary = images.get('Primary', {})
            large = primary.get('Large', {})
            if large.get('URL'):
                image_urls.append(large['URL'])
            
            # Variant images
            variants = images.get('Variants', [])
            for variant in variants:
                if len(image_urls) >= 3:
                    break
                large_variant = variant.get('Large', {})
                if large_variant.get('URL') and large_variant['URL'] not in image_urls:
                    image_urls.append(large_variant['URL'])

            product_data['image_urls'] = image_urls[:3]
            
            return product_data

        except Exception as e:
            print(f"DEBUG: Failed to extract V2 product data: {e}")
            return None

    def _extract_enhanced_product_data(self, item) -> Optional[Dict[str, Any]]:
        """
        Extract enhanced product data including sales rank for the discovery cycle.
        """
        try:
            asin = getattr(item, 'asin', '')
            if not asin:
                return None

            product_data = {
                'asin': asin,
                'title': '',
                'price': None,
                'currency': 'EUR',
                'rating': None,
                'review_count': None,
                'sales_rank': None,
                'image_urls': [],  # Use list format for consistency
                'affiliate_link': getattr(item, 'detail_page_url', ''),
            }

            # Extract title
            if hasattr(item, 'item_info') and item.item_info:
                if hasattr(item.item_info, 'title') and item.item_info.title:
                    product_data['title'] = getattr(item.item_info.title, 'display_value', '')

            # Extract price
            if hasattr(item, 'offers') and item.offers:
                if hasattr(item.offers, 'listings') and item.offers.listings:
                    for listing in item.offers.listings:
                        if hasattr(listing, 'price') and listing.price:
                            amount = getattr(listing.price, 'amount', None)
                            currency = getattr(listing.price, 'currency', 'EUR')
                            if amount is not None:
                                product_data['price'] = float(amount) / 100  # Convert from cents
                                product_data['currency'] = currency
                            break

            # Extract rating and review count - try multiple paths for SearchItems API
            # SearchItems API may have different structure than GetItems API
            try:
                # Try direct customer_reviews access first
                if hasattr(item, 'customer_reviews') and item.customer_reviews:
                    reviews = item.customer_reviews
                    if hasattr(reviews, 'count') and reviews.count:
                        product_data['review_count'] = int(reviews.count)
                    if hasattr(reviews, 'star_rating') and reviews.star_rating:
                        if hasattr(reviews.star_rating, 'rating') and reviews.star_rating.rating:
                            product_data['rating'] = float(reviews.star_rating.rating)

                # Fallback to item_info.product_info path
                elif hasattr(item, 'item_info') and item.item_info:
                    if hasattr(item.item_info, 'product_info') and item.item_info.product_info:
                        if hasattr(item.item_info.product_info, 'customer_reviews') and item.item_info.product_info.customer_reviews:
                            reviews = item.item_info.product_info.customer_reviews
                            if hasattr(reviews, 'count') and reviews.count:
                                product_data['review_count'] = int(reviews.count)
                            if hasattr(reviews, 'star_rating') and reviews.star_rating:
                                if hasattr(reviews.star_rating, 'rating') and reviews.star_rating.rating:
                                    product_data['rating'] = float(reviews.star_rating.rating)

                # If still no data, try to get from any available customer review info
                if product_data['rating'] is None or product_data['review_count'] is None:
                    # Try to access customer reviews from any available location
                    if hasattr(item, 'item_info') and item.item_info:
                        # Look for any customer review related data
                        item_info_dict = item.item_info.to_dict() if hasattr(item.item_info, 'to_dict') else {}
                        customer_reviews = item_info_dict.get('customer_reviews', {})

                        if customer_reviews:
                            if 'count' in customer_reviews and customer_reviews['count']:
                                product_data['review_count'] = int(customer_reviews['count'])
                            if 'star_rating' in customer_reviews and customer_reviews['star_rating']:
                                rating_data = customer_reviews['star_rating']
                                if isinstance(rating_data, dict) and 'rating' in rating_data:
                                    product_data['rating'] = float(rating_data['rating'])
                                elif hasattr(rating_data, 'rating'):
                                    product_data['rating'] = float(rating_data.rating)

            except Exception as e:
                print(f"DEBUG: Failed to extract rating/review data: {e}")

            # Extract sales rank - try multiple paths
            try:
                # Try direct browse_node_info access
                if hasattr(item, 'browse_node_info') and item.browse_node_info:
                    if hasattr(item.browse_node_info, 'website_sales_rank') and item.browse_node_info.website_sales_rank:
                        sales_rank_data = item.browse_node_info.website_sales_rank
                        if isinstance(sales_rank_data, dict):
                            product_data['sales_rank'] = sales_rank_data.get('sales_rank')
                        elif hasattr(sales_rank_data, 'sales_rank'):
                            product_data['sales_rank'] = sales_rank_data.sales_rank
                        else:
                            # Try to convert to dict and extract
                            sales_rank_dict = sales_rank_data.to_dict() if hasattr(sales_rank_data, 'to_dict') else {}
                            product_data['sales_rank'] = sales_rank_dict.get('sales_rank')

                # Fallback: try to get from item_info
                if product_data['sales_rank'] is None and hasattr(item, 'item_info') and item.item_info:
                    item_info_dict = item.item_info.to_dict() if hasattr(item.item_info, 'to_dict') else {}
                    browse_node_info = item_info_dict.get('browse_node_info', {})

                    if browse_node_info and 'website_sales_rank' in browse_node_info:
                        sales_rank_data = browse_node_info['website_sales_rank']
                        if isinstance(sales_rank_data, dict):
                            product_data['sales_rank'] = sales_rank_data.get('sales_rank')
                        elif hasattr(sales_rank_data, 'sales_rank'):
                            product_data['sales_rank'] = sales_rank_data.sales_rank

            except Exception as e:
                print(f"DEBUG: Failed to extract sales rank: {e}")

            # Extract image
            if hasattr(item, 'images') and item.images:
                if hasattr(item.images, 'primary') and item.images.primary:
                    if hasattr(item.images.primary, 'large') and item.images.primary.large:
                        primary_url = getattr(item.images.primary.large, 'url', '')
                        if primary_url:
                            product_data['image_urls'] = [primary_url]  # Use list format

            # Debug logging
            # print(f"DEBUG: Extracted product {asin}: rating={product_data['rating']}, reviews={product_data['review_count']}, sales_rank={product_data['sales_rank']}")

            return product_data

        except Exception as e:
            print(f"DEBUG: Failed to extract product data: {e}")
            import traceback
            traceback.print_exc()
            return None

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
