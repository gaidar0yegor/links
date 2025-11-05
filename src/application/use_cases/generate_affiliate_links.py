from typing import List
from ...domain.entities.product import Product
from ...infrastructure.database.repositories import IProductRepository
from ...infrastructure.external.interfaces import IPartnerApi


class GenerateAffiliateLinksUseCase:
    """
    Use Case: Генерация Партнёрских Ссылок

    Для каждого товара в подборке вызывает IPartnerApi.GenerateAffiliateLink(product_id),
    сохраняет полученную ссылку в БД.
    """

    def __init__(
        self,
        product_repository: IProductRepository,
        partner_api: IPartnerApi
    ):
        self.product_repository = product_repository
        self.partner_api = partner_api

    async def execute(self, channel_id: int) -> List[Product]:
        """
        Generate affiliate links for products in a channel.

        Args:
            channel_id: ID of the channel to process

        Returns:
            List[Product]: Products with affiliate links generated
        """
        # Получить продукты канала без партнерских ссылок
        products = await self.product_repository.get_by_channel_id(channel_id)

        updated_products = []

        for product in products:
            if not product.affiliate_link:  # Only generate if not already exists
                try:
                    # Вызвать IPartnerApi.GenerateAffiliateLink(product_id)
                    affiliate_link = await self.partner_api.generate_affiliate_link(
                        product.source_id
                    )

                    # Обновить продукт с партнерской ссылкой
                    product.affiliate_link = affiliate_link

                    # Сохранить полученную ссылку в БД
                    updated_product = await self.product_repository.save(product)
                    updated_products.append(updated_product)

                except Exception as e:
                    # Log error but continue with other products
                    print(f"Error generating affiliate link for product {product.id}: {e}")
                    continue

        return updated_products
