from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class ChannelSettings:
    """Domain entity representing channel filtering settings."""
    id: Optional[int]
    channel_id: int  # Канал_ID
    categories: List[str]  # Категория (string, list)
    is_best_seller: bool  # IsBestSeller (bool)
    min_rating: float  # MinRating (float)
    min_reviews: int  # MinReviews (int)
    items_per_day: int  # ItemsPerDay (int)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
