from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Product:
    """Domain entity representing a product from partner platform."""
    id: Optional[int]
    channel_id: int  # Channel_ID
    source_id: str  # Source_ID (Уникальный ID с ресурса)
    title: str  # Название
    description: str  # Описание
    image_url: str  # Изображение (URL)
    price: float  # Цена
    rating: float  # Рейтинг
    review_count: int  # Кол-во Отзывов
    category: str  # Категория
    is_best_seller: bool  # IsBestSeller
    affiliate_link: Optional[str] = None  # Партнёрская_Ссылка
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
