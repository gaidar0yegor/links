from typing import List
from datetime import datetime, time
from ...domain.entities.product import Product
from ...infrastructure.database.repositories import IProductRepository, IChannelRepository
from ...infrastructure.external.interfaces import ITelegramPublisher, IAiRewriter


class GenerateContentAndPublishUseCase:
    """
    Use Case: Формирование Контента и Публикация

    Для каждого товара: вызывает RewriteDescription для краткого описания,
    формирует полный пост в формате карточки товара,
    рассчитывает время публикации, вызывает SchedulePost для отправки в отложку.
    """

    def __init__(
        self,
        product_repository: IProductRepository,
        channel_repository: IChannelRepository,
        telegram_publisher: ITelegramPublisher,
        ai_rewriter: IAiRewriter
    ):
        self.product_repository = product_repository
        self.channel_repository = channel_repository
        self.telegram_publisher = telegram_publisher
        self.ai_rewriter = ai_rewriter

    async def execute(self, channel_id: int) -> dict:
        """
        Generate content and schedule publishing for a channel.

        Args:
            channel_id: ID of the channel to process

        Returns:
            dict: Results with publishing schedule
        """
        # Получить канал и продукты
        channel = await self.channel_repository.get_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        products = await self.product_repository.get_by_channel_id(channel_id)
        products_with_links = [p for p in products if p.affiliate_link]

        if not products_with_links:
            return {'error': 'No products with affiliate links found'}

        # Рассчитать время публикации
        publish_times = self._calculate_publish_times(
            len(products_with_links),
            start_time=time(8, 0),  # 8:00
            end_time=time(21, 0)    # 21:00
        )

        results = []

        for i, product in enumerate(products_with_links):
            try:
                # Вызвать RewriteDescription для получения краткого описания
                rewritten_description = await self.ai_rewriter.rewrite_description(
                    product.title,
                    product.description
                )

                # Сформировать полный пост в формате карточки товара
                post_content = self._format_product_post(product, rewritten_description)

                # Расчет времени публикации
                publish_time = publish_times[i]

                # Вызвать SchedulePost для отправки поста в отложку
                message_id = await self.telegram_publisher.schedule_post(
                    channel.telegram_chat_id,
                    post_content,
                    publish_time
                )

                results.append({
                    'product_id': product.id,
                    'message_id': message_id,
                    'scheduled_time': publish_time.isoformat(),
                    'success': True
                })

            except Exception as e:
                results.append({
                    'product_id': product.id,
                    'error': str(e),
                    'success': False
                })

        return {
            'channel_id': channel_id,
            'total_products': len(products_with_links),
            'scheduled_posts': len([r for r in results if r['success']]),
            'results': results
        }

    def _calculate_publish_times(self, num_products: int, start_time: time, end_time: time) -> List[datetime]:
        """
        Рассчитать время публикации, разделив ItemsPerDay на рабочий интервал.
        """
        if num_products == 0:
            return []

        # Calculate total available minutes
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        total_minutes = end_minutes - start_minutes

        # Distribute posts evenly throughout the day
        interval_minutes = total_minutes // num_products if num_products > 0 else 0

        publish_times = []
        current_minutes = start_minutes

        for i in range(num_products):
            # Convert back to datetime
            hours = current_minutes // 60
            minutes = current_minutes % 60
            publish_time = datetime.combine(datetime.today(), time(hours, minutes))

            publish_times.append(publish_time)
            current_minutes += interval_minutes

            # Ensure we don't go past end time
            if current_minutes >= end_minutes:
                break

        return publish_times

    def _format_product_post(self, product: Product, rewritten_description: str) -> str:
        """
        Сформировать полный пост в формате карточки товара.
        """
        return f"""🛍️ {product.title}

{rewritten_description}

💰 Цена: {product.price} ₽
⭐ Рейтинг: {product.rating}/5.0 ({product.review_count} отзывов)
🏷️ Категория: {product.category}

🔗 {product.affiliate_link}

#товары #{product.category.replace(' ', '').replace('&', 'и')}
"""
