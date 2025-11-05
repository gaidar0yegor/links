from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Channel:
    """Domain entity representing a Telegram channel."""
    id: Optional[int]
    name: str
    telegram_chat_id: str  # ID_Чата (Telegram)
    product_source_url: str  # Сайт_Товаров (URL)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
