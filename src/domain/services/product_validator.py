from typing import List
from ..entities.product import Product
from ..entities.settings import ChannelSettings


class ProductValidator:
    """Domain service for product validation business rules."""

    @staticmethod
    def is_product_valid(product: Product, settings: ChannelSettings) -> bool:
        """
        Проверяет соответствие товара всем фильтрам настроек канала.

        Args:
            product: Product entity to validate
            settings: ChannelSettings with filtering criteria

        Returns:
            bool: True if product matches all criteria, False otherwise
        """
        # Check category filter
        if settings.categories and product.category not in settings.categories:
            return False

        # Check best seller filter
        if settings.is_best_seller and not product.is_best_seller:
            return False

        # Check minimum rating
        if product.rating < settings.min_rating:
            return False

        # Check minimum review count
        if product.review_count < settings.min_reviews:
            return False

        return True
