import json
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, and_, func

from .models import ChannelModel, ChannelSettingsModel, ProductModel, PublicationModel
from .repositories import IChannelRepository, ISettingsRepository, IProductRepository, IPublicationRepository
from ...domain.entities.channel import Channel
from ...domain.entities.settings import ChannelSettings
from ...domain.entities.product import Product
from ...domain.entities.publication import Publication


class PostgresChannelRepository(IChannelRepository):
    """PostgreSQL implementation of IChannelRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, channel_id: int) -> Optional[Channel]:
        result = await self.session.execute(
            select(ChannelModel).where(ChannelModel.id == channel_id)
        )
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def get_all_active(self) -> List[Channel]:
        result = await self.session.execute(
            select(ChannelModel).where(ChannelModel.is_active == True)
        )
        models = result.scalars().all()
        return [self._model_to_entity(model) for model in models]

    async def save(self, channel: Channel) -> Channel:
        if channel.id:
            # Update existing
            stmt = (
                update(ChannelModel)
                .where(ChannelModel.id == channel.id)
                .values(
                    name=channel.name,
                    telegram_chat_id=channel.telegram_chat_id,
                    product_source_url=channel.product_source_url,
                    is_active=channel.is_active
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            return channel
        else:
            # Create new
            model = ChannelModel(
                name=channel.name,
                telegram_chat_id=channel.telegram_chat_id,
                product_source_url=channel.product_source_url,
                is_active=channel.is_active
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            return self._model_to_entity(model)

    async def delete(self, channel_id: int) -> bool:
        result = await self.session.execute(
            delete(ChannelModel).where(ChannelModel.id == channel_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    def _model_to_entity(self, model: ChannelModel) -> Channel:
        return Channel(
            id=model.id,
            name=model.name,
            telegram_chat_id=model.telegram_chat_id,
            product_source_url=model.product_source_url,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )


class PostgresSettingsRepository(ISettingsRepository):
    """PostgreSQL implementation of ISettingsRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_channel_id(self, channel_id: int) -> Optional[ChannelSettings]:
        result = await self.session.execute(
            select(ChannelSettingsModel).where(ChannelSettingsModel.channel_id == channel_id)
        )
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def get_all_active(self) -> List[ChannelSettings]:
        # Get settings for active channels
        result = await self.session.execute(
            select(ChannelSettingsModel)
            .join(ChannelModel)
            .where(ChannelModel.is_active == True)
        )
        models = result.scalars().all()
        return [self._model_to_entity(model) for model in models]

    async def save(self, settings: ChannelSettings) -> ChannelSettings:
        categories_json = json.dumps(settings.categories)

        if settings.id:
            # Update existing
            stmt = (
                update(ChannelSettingsModel)
                .where(ChannelSettingsModel.id == settings.id)
                .values(
                    categories=categories_json,
                    is_best_seller=settings.is_best_seller,
                    min_rating=settings.min_rating,
                    min_reviews=settings.min_reviews,
                    items_per_day=settings.items_per_day
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            return settings
        else:
            # Create new
            model = ChannelSettingsModel(
                channel_id=settings.channel_id,
                categories=categories_json,
                is_best_seller=settings.is_best_seller,
                min_rating=settings.min_rating,
                min_reviews=settings.min_reviews,
                items_per_day=settings.items_per_day
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            return self._model_to_entity(model)

    async def delete(self, channel_id: int) -> bool:
        result = await self.session.execute(
            delete(ChannelSettingsModel).where(ChannelSettingsModel.channel_id == channel_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    def _model_to_entity(self, model: ChannelSettingsModel) -> ChannelSettings:
        return ChannelSettings(
            id=model.id,
            channel_id=model.channel_id,
            categories=json.loads(model.categories),
            is_best_seller=model.is_best_seller,
            min_rating=model.min_rating,
            min_reviews=model.min_reviews,
            items_per_day=model.items_per_day,
            created_at=model.created_at,
            updated_at=model.updated_at
        )


class PostgresProductRepository(IProductRepository):
    """PostgreSQL implementation of IProductRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        result = await self.session.execute(
            select(ProductModel).where(ProductModel.id == product_id)
        )
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def get_by_channel_id(self, channel_id: int, limit: int = 100) -> List[Product]:
        result = await self.session.execute(
            select(ProductModel)
            .where(ProductModel.channel_id == channel_id)
            .order_by(ProductModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._model_to_entity(model) for model in models]

    async def save(self, product: Product) -> Product:
        if product.id:
            # Update existing
            stmt = (
                update(ProductModel)
                .where(ProductModel.id == product.id)
                .values(
                    title=product.title,
                    description=product.description,
                    image_url=product.image_url,
                    price=product.price,
                    rating=product.rating,
                    review_count=product.review_count,
                    category=product.category,
                    is_best_seller=product.is_best_seller,
                    affiliate_link=product.affiliate_link
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            return product
        else:
            # Create new
            model = ProductModel(
                channel_id=product.channel_id,
                source_id=product.source_id,
                title=product.title,
                description=product.description,
                image_url=product.image_url,
                price=product.price,
                rating=product.rating,
                review_count=product.review_count,
                category=product.category,
                is_best_seller=product.is_best_seller,
                affiliate_link=product.affiliate_link
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            return self._model_to_entity(model)

    async def save_batch(self, products: List[Product]) -> List[Product]:
        """Save multiple products in batch."""
        saved_products = []
        for product in products:
            saved_product = await self.save(product)
            saved_products.append(saved_product)
        return saved_products

    async def delete_old_products(self, channel_id: int, days_old: int = 30) -> int:
        """Delete products older than specified days for a channel."""
        cutoff_date = func.now() - func.interval(f'{days_old} days')

        result = await self.session.execute(
            delete(ProductModel).where(
                and_(
                    ProductModel.channel_id == channel_id,
                    ProductModel.created_at < cutoff_date
                )
            )
        )
        await self.session.commit()
        return result.rowcount

    def _model_to_entity(self, model: ProductModel) -> Product:
        return Product(
            id=model.id,
            channel_id=model.channel_id,
            source_id=model.source_id,
            title=model.title,
            description=model.description,
            image_url=model.image_url,
            price=model.price,
            rating=model.rating,
            review_count=model.review_count,
            category=model.category,
            is_best_seller=model.is_best_seller,
            affiliate_link=model.affiliate_link,
            created_at=model.created_at,
            updated_at=model.updated_at
        )


class PostgresPublicationRepository(IPublicationRepository):
    """PostgreSQL implementation of IPublicationRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, publication: Publication) -> Publication:
        model = PublicationModel(
            product_id=publication.product_id,
            published_at=publication.published_at,
            status=publication.status,
            telegram_message_id=publication.telegram_message_id,
            error_message=publication.error_message
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._model_to_entity(model)

    async def get_recent_by_channel(self, channel_id: int, limit: int = 50) -> List[Publication]:
        # Get publications for products in this channel
        result = await self.session.execute(
            select(PublicationModel)
            .join(ProductModel)
            .where(ProductModel.channel_id == channel_id)
            .order_by(PublicationModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._model_to_entity(model) for model in models]

    async def get_by_date_range(self, start_date, end_date) -> List[Publication]:
        result = await self.session.execute(
            select(PublicationModel)
            .where(PublicationModel.published_at.between(start_date, end_date))
            .order_by(PublicationModel.published_at.desc())
        )
        models = result.scalars().all()
        return [self._model_to_entity(model) for model in models]

    def _model_to_entity(self, model: PublicationModel) -> Publication:
        return Publication(
            id=model.id,
            product_id=model.product_id,
            published_at=model.published_at,
            status=model.status,
            telegram_message_id=model.telegram_message_id,
            error_message=model.error_message,
            created_at=model.created_at
        )
