#!/usr/bin/env python3
"""
Simplified Product Filter Service for Telegram Affiliate Bot
STREAMLINED QUALITY CONTROL: Only uses Sales Rank filtering.
"""

from typing import List, Dict, Optional, Any
from services.logger import bot_logger


class ProductFilter:
    """
    Simplified product filtering service.
    Only uses sales rank as quality metric - the streamlined approach.
    """

    def __init__(self):
        # Simplified: No complex Google Sheets filters needed
        # Only sales rank threshold is used for quality control
        self.filters_cache = {
            'default': {
                'id': 'default',
                'name': 'Sales Rank Only (Streamlined)',
                'criteria': {'max_sales_rank': 10000}
            }
        }

    def get_filter_by_id(self, filter_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific filter by ID."""
        return self.filters_cache.get(filter_id, self.filters_cache.get('default'))

    def get_all_filters(self) -> Dict[str, Dict[str, Any]]:
        """Get all available filters (simplified to just sales rank)."""
        return self.filters_cache.copy()

    def apply_sales_rank_filter(self, products: List[Dict[str, Any]], max_sales_rank: int = 10000) -> List[Dict[str, Any]]:
        """
        Apply simplified sales rank filtering only.

        Args:
            products: List of product dictionaries
            max_sales_rank: Maximum sales rank threshold (lower = better selling)

        Returns:
            Filtered list of products that meet sales rank criteria
        """
        filtered_products = []

        for product in products:
            sales_rank = product.get('sales_rank') or product.get('SalesRank')
            if sales_rank is None:
                # If no sales rank data, exclude the product
                continue

            try:
                sales_rank = int(sales_rank)
                if sales_rank <= max_sales_rank:
                    filtered_products.append(product)
            except (ValueError, TypeError):
                # If sales rank can't be parsed, exclude the product
                continue

        bot_logger.log_info("ProductFilter",
                          f"Applied sales rank filter (≤{max_sales_rank}) to {len(products)} products, "
                          f"{len(filtered_products)} passed")

        return filtered_products

    def apply_filter(self, products: List[Dict[str, Any]], filter_id: str) -> List[Dict[str, Any]]:
        """
        Legacy method for backward compatibility.
        Now simplified to only use sales rank filtering.
        """
        filter_config = self.get_filter_by_id(filter_id)
        if not filter_config:
            bot_logger.log_error("ProductFilter", Exception(f"Filter not found: {filter_id}"), "Returning original products")
            return products

        # Extract max_sales_rank from criteria, default to 10000
        max_sales_rank = filter_config.get('criteria', {}).get('max_sales_rank', 10000)

        return self.apply_sales_rank_filter(products, max_sales_rank)

    def get_products_by_filter(self, filter_id: str, all_products: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Get products that match a specific filter.
        Simplified to only use sales rank filtering.
        """
        if all_products is None:
            # In streamlined system, products come from queue, not Google Sheets
            bot_logger.log_warning("ProductFilter", "No products provided - streamlined system uses queue instead")
            return []

        return self.apply_filter(all_products, filter_id)

    def get_filter_summary(self, filter_id: str) -> Optional[str]:
        """Get a human-readable summary of a filter."""
        filter_config = self.get_filter_by_id(filter_id)
        if not filter_config:
            return None

        max_rank = filter_config.get('criteria', {}).get('max_sales_rank', 10000)
        return f"Sales Rank ≤ {max_rank} (Streamlined Quality Control)"


# Global instance
product_filter = ProductFilter()
