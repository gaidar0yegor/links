from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Publication:
    """Domain entity for publication logging."""
    id: Optional[int]
    product_id: int
    published_at: datetime
    status: str  # 'success', 'failed', 'scheduled'
    telegram_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
