from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from ...domain.entities.channel import Channel
from ...domain.entities.settings import ChannelSettings
from ...domain.entities.product import Product


class IChannelRepository(ABC):
    """Interface for channel data access."""

    @abstractmethod
    async def get_by_id(self, channel_id: int) -> Optional[Channel]:
        """Get channel by ID."""
        pass

    @abstractmethod
    async def get_all_active(self) -> List[Channel]:
        """Get all active channels."""
        pass

    @abstractmethod
    async def save(self, channel: Channel) -> Channel:
        """Save or update channel."""
        pass

    @abstractmethod
    async def delete(self, channel_id: int) -> bool:
        """Delete channel by ID."""
        pass


class ISettingsRepository(ABC):
    """Interface for channel settings data access."""

    @abstractmethod
    async def get_by_channel_id(self, channel_id: int) -> Optional[ChannelSettings]:
        """Get settings for a specific channel."""
        pass

    @abstractmethod
    async def get_all_active(self) -> List[ChannelSettings]:
        """Get settings for all active channels."""
        pass

    @abstractmethod
    async def save(self, settings: ChannelSettings) -> ChannelSettings:
        """Save or update channel settings."""
        pass

    @abstractmethod
    async def delete(self, channel_id: int) -> bool:
        """Delete settings for a channel."""
        pass


class IProductRepository(ABC):
    """Interface for product data access."""

    @abstractmethod
    async def get_by_id(self, product_id: int) -> Optional[Product]:
        """Get product by ID."""
        pass

    @abstractmethod
    async def get_by_channel_id(self, channel_id: int, limit: int = 100) -> List[Product]:
        """Get products for a specific channel."""
        pass

    @abstractmethod
    async def save(self, product: Product) -> Product:
        """Save or update product."""
        pass

    @abstractmethod
    async def save_batch(self, products: List[Product]) -> List[Product]:
        """Save multiple products in batch."""
        pass

    @abstractmethod
    async def delete_old_products(self, channel_id: int, days_old: int = 30) -> int:
        """Delete products older than specified days for a channel."""
        pass


class IPublicationRepository(ABC):
    """Interface for publication logging data access."""

    @abstractmethod
    async def save(self, publication: 'Publication') -> 'Publication':
        """Save publication record."""
        pass

    @abstractmethod
    async def get_recent_by_channel(self, channel_id: int, limit: int = 50) -> List['Publication']:
        """Get recent publications for a channel."""
        pass

    @abstractmethod
    async def get_by_date_range(self, start_date: datetime, end_date: datetime) -> List['Publication']:
        """Get publications within date range."""
        pass
