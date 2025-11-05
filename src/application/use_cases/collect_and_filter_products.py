from typing import List
from ...domain.entities.product import Product
from ...domain.entities.settings import ChannelSettings
from ...domain.services.product_validator import ProductValidator
from ...infrastructure.database.repositories import ISettingsRepository, IProductRepository
from ...infrastructure.external.interfaces import IPartnerApi


class CollectAndFilterProductsUseCase:
    """
    Use Case: Сбор и Фильтрация Товаров

    Загружает настройки для всех активных каналов,
    для каждого канала вызывает IPartnerApi.FetchProducts с лимитом,
    использует IsProductValid для первичной фильтрации,
    формирует окончательную подборку в количестве ItemsPerDay.
    """

    def __init__(
        self,
        settings_repository: ISettingsRepository,
        product_repository: IProductRepository,
        partner_api: IPartnerApi
    ):
        self.settings_repository = settings_repository
        self.product_repository = product_repository
        self.partner_api = partner_api

    async def execute(self) -> dict:
        """
        Execute the use case.

        Returns:
            dict: Results with products collected per channel
        """
        results = {}

        # Загрузить настройки для всех активных каналов
        active_settings = await self.settings_repository.get_all_active()

        for settings in active_settings:
            try:
                # Вызвать IPartnerApi.FetchProducts с лимитом, достаточным для суточного отбора
                fetch_limit = settings.items_per_day * 3  # Fetch 3x the daily limit for better selection
                raw_products = await self.partner_api.fetch_products(
                    categories=settings.categories,
                    limit=fetch_limit
                )

                # Использовать IsProductValid для первичной фильтрации
                valid_products = [
                    product for product in raw_products
                    if ProductValidator.is_product_valid(product, settings)
                ]

                # Сформировать окончательную подборку в количестве ItemsPerDay
                selected_products = valid_products[:settings.items_per_day]

                # Сохранить продукты в БД
                if selected_products:
                    saved_products = await self.product_repository.save_batch(selected_products)
                    results[settings.channel_id] = {
                        'products': saved_products,
                        'count': len(saved_products)
                    }

            except Exception as e:
                # Log error but continue with other channels
                results[settings.channel_id] = {
                    'error': str(e),
                    'count': 0
                }

        return results
