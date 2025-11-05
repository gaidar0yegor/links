from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from ...domain.entities.product import Product


class IPartnerApi(ABC):
    """Interface for partner platform API (Amazon, etc.)."""

    @abstractmethod
    async def get_available_categories(self) -> List[str]:
        """Get list of available product categories."""
        pass

    @abstractmethod
    async def fetch_products(self, categories: List[str], limit: int = 100) -> List[Product]:
        """Fetch products from partner platform based on categories."""
        pass

    @abstractmethod
    async def generate_affiliate_link(self, product_source_id: str) -> str:
        """Generate affiliate link for a product."""
        pass


class ITelegramPublisher(ABC):
    """Interface for Telegram publishing service."""

    @abstractmethod
    async def schedule_post(self, channel_id: str, content: str, scheduled_time: datetime) -> str:
        """Schedule a post to Telegram channel."""
        pass

    @abstractmethod
    async def send_post_immediately(self, channel_id: str, content: str) -> bool:
        """Send post to Telegram channel immediately."""
        pass


class IAiRewriter(ABC):
    """Interface for AI content rewriting service."""

    @abstractmethod
    async def rewrite_description(self, title: str, original_description: str) -> str:
        """Rewrite product description using AI."""
        pass

    @abstractmethod
    async def generate_post_content(self, product: Product) -> str:
        """Generate complete post content for Telegram."""
        pass
