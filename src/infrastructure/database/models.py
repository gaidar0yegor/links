from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class ChannelModel(Base):
    """SQLAlchemy model for channels table."""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    telegram_chat_id = Column(String(255), nullable=False, unique=True)
    product_source_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChannelSettingsModel(Base):
    """SQLAlchemy model for channel_settings table."""
    __tablename__ = "channel_settings"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, unique=True)
    categories = Column(Text, nullable=False)  # JSON array as text
    is_best_seller = Column(Boolean, default=False)
    min_rating = Column(Float, default=4.0)
    min_reviews = Column(Integer, default=10)
    items_per_day = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductModel(Base):
    """SQLAlchemy model for products table."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    source_id = Column(String(255), nullable=False)  # Unique ID from partner platform
    title = Column(String(500), nullable=False)
    description = Column(Text)
    image_url = Column(String(500))
    price = Column(Float, nullable=False)
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    category = Column(String(255))
    is_best_seller = Column(Boolean, default=False)
    affiliate_link = Column(String(1000))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {'schema': 'public'}
    )


class PublicationModel(Base):
    """SQLAlchemy model for publications table."""
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(50), nullable=False)  # 'success', 'failed', 'scheduled'
    telegram_message_id = Column(String(255))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {'schema': 'public'}
    )
