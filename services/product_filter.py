#!/usr/bin/env python3
"""
Product Filter Service for Telegram Affiliate Bot
Handles product filtering based on Google Sheets criteria.
"""

from typing import List, Dict, Optional, Any
from services.sheets_api import sheets_api
from services.logger import bot_logger


class ProductFilter:
    """Service for filtering products based on various criteria."""

    def __init__(self):
        self.filters_cache = {}
        self._load_filters()

    def _load_filters(self):
        """Load product filters from Google Sheets."""
        try:
            filters_data = sheets_api.get_sheet_data('product_filters')
            if filters_data and len(filters_data) > 1:
                headers = filters_data[0]
                col_indices = {header: idx for idx, header in enumerate(headers)}

                self.filters_cache = {}
                for row in filters_data[1:]:
                    if len(row) >= len(headers):
                        filter_id = row[col_indices.get('filter_id', 0)]
                        name = row[col_indices.get('name', 1)]

                        # Parse numeric criteria
                        criteria = {}
                        numeric_fields = ['min_rating', 'min_reviews', 'min_orders', 'price_min', 'price_max', 'profit_min', 'seller_rank_min']

                        for field in numeric_fields:
                            try:
                                value = row[col_indices.get(field, -1)]
                                if value and value.strip():
                                    criteria[field] = float(value)
                            except (ValueError, IndexError, TypeError):
                                pass

                        self.filters_cache[filter_id] = {
                            'id': filter_id,
                            'name': name,
                            'criteria': criteria
                        }

            bot_logger.log_info("ProductFilter", f"Loaded {len(self.filters_cache)} product filters")

        except Exception as e:
            bot_logger.log_error("ProductFilter", e, "Failed to load product filters from Google Sheets")
            self.filters_cache = {}

    def get_filter_by_id(self, filter_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific filter by ID."""
        return self.filters_cache.get(filter_id)

    def get_all_filters(self) -> Dict[str, Dict[str, Any]]:
        """Get all available filters."""
        return self.filters_cache.copy()

    def apply_filter(self, products: List[Dict[str, Any]], filter_id: str) -> List[Dict[str, Any]]:
        """
        Apply a filter to a list of products.

        Args:
            products: List of product dictionaries
            filter_id: ID of the filter to apply

        Returns:
            Filtered list of products
        """
        filter_config = self.get_filter_by_id(filter_id)
        if not filter_config:
            bot_logger.log_error("ProductFilter", Exception(f"Filter not found: {filter_id}"), "Returning original products")
            return products

        criteria = filter_config.get('criteria', {})
        filtered_products = []

        for product in products:
            if self._matches_criteria(product, criteria):
                filtered_products.append(product)

        bot_logger.log_info("ProductFilter", f"Applied filter '{filter_config['name']}' to {len(products)} products, {len(filtered_products)} passed")
        return filtered_products

    def _matches_criteria(self, product: Dict[str, Any], criteria: Dict[str, float]) -> bool:
        """
        Check if a product matches the filter criteria.

        Args:
            product: Product dictionary
            criteria: Filter criteria dictionary

        Returns:
            True if product matches all criteria
        """
        try:
            # Rating filter
            if 'min_rating' in criteria:
                product_rating = float(product.get('rating', 0))
                if product_rating < criteria['min_rating']:
                    return False

            # Reviews filter
            if 'min_reviews' in criteria:
                product_reviews = int(product.get('reviews_count', 0))
                if product_reviews < criteria['min_reviews']:
                    return False

            # Orders filter (if available in product data)
            if 'min_orders' in criteria:
                product_orders = int(product.get('orders_count', 0))  # This might not be in our current data
                if product_orders < criteria['min_orders']:
                    return False

            # Price range filter
            if 'price_min' in criteria or 'price_max' in criteria:
                try:
                    product_price = float(product.get('price', 0))
                    if 'price_min' in criteria and product_price < criteria['price_min']:
                        return False
                    if 'price_max' in criteria and product_price > criteria['price_max']:
                        return False
                except (ValueError, TypeError):
                    # If price can't be parsed, exclude the product
                    return False

            # Profit filter (if available)
            if 'profit_min' in criteria:
                product_profit = float(product.get('estimated_profit', 0))
                if product_profit < criteria['profit_min']:
                    return False

            # Seller rank filter (if available)
            if 'seller_rank_min' in criteria:
                seller_rank = int(product.get('seller_rank', 999999))
                if seller_rank > criteria['seller_rank_min']:  # Lower rank number is better
                    return False

            return True

        except Exception as e:
            bot_logger.log_error("ProductFilter", e, f"Error checking criteria for product: {product.get('name', 'Unknown')}")
            return False

    def get_products_by_filter(self, filter_id: str, all_products: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Get products that match a specific filter.

        Args:
            filter_id: ID of the filter to apply
            all_products: List of all products (if None, will load from Google Sheets)

        Returns:
            Filtered list of products
        """
        if all_products is None:
            # Load all products from Google Sheets
            all_products = self._load_all_products()

        return self.apply_filter(all_products, filter_id)

    def _load_all_products(self) -> List[Dict[str, Any]]:
        """Load all active products from Google Sheets."""
        try:
            products_data = sheets_api.get_sheet_data('products')
            if not products_data or len(products_data) < 2:
                return []

            headers = products_data[0]
            col_indices = {header: idx for idx, header in enumerate(headers)}

            products = []
            for row in products_data[1:]:
                if len(row) >= len(headers):
                    # Check if product is active
                    active = row[col_indices.get('active', -1)].upper() if col_indices.get('active', -1) >= 0 else 'TRUE'
                    if active == 'TRUE':
                        product = {
                            'id': row[col_indices.get('id', 0)],
                            'name': row[col_indices.get('name', 1)],
                            'category': row[col_indices.get('category', 2)],
                            'subcategory': row[col_indices.get('subcategory', 3)],
                            'price': row[col_indices.get('price', 4)],
                            'rating': row[col_indices.get('rating', 5)],
                            'reviews_count': row[col_indices.get('reviews_count', 6)],
                            'image_url': row[col_indices.get('image_url', 7)],
                            'affiliate_link': row[col_indices.get('affiliate_link', 8)],
                            'description': row[col_indices.get('description', 9)],
                            'active': active
                        }
                        products.append(product)

            return products

        except Exception as e:
            bot_logger.log_error("ProductFilter", e, "Failed to load products from Google Sheets")
            return []

    def get_filter_summary(self, filter_id: str) -> Optional[str]:
        """Get a human-readable summary of a filter."""
        filter_config = self.get_filter_by_id(filter_id)
        if not filter_config:
            return None

        name = filter_config.get('name', 'Unknown')
        criteria = filter_config.get('criteria', {})

        criteria_parts = []
        if 'min_rating' in criteria:
            criteria_parts.append(f"Rating ≥ {criteria['min_rating']}")
        if 'min_reviews' in criteria:
            criteria_parts.append(f"Reviews ≥ {criteria['min_reviews']}")
        if 'price_min' in criteria:
            criteria_parts.append(f"Price ≥ ${criteria['price_min']}")
        if 'price_max' in criteria:
            criteria_parts.append(f"Price ≤ ${criteria['price_max']}")

        criteria_str = ', '.join(criteria_parts) if criteria_parts else 'No criteria'

        return f"{name}: {criteria_str}"


# Global instance
product_filter = ProductFilter()
