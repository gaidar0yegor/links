# services/post_manager.py
import requests
from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont # Для водяных знаков
from io import BytesIO
from services.sheets_api import sheets_api
from services.amazon_paapi_client import amazon_paapi_client
from services.llm_client import OpenAIClient

class PostManager:
    """Управляет бизнес-логикой: API, Рерайт, Водяные знаки, Постинг."""
    def __init__(self, bot):
        self.bot = bot
        # Инициализация LLM клиента
        try:
            self.llm_client = OpenAIClient()
        except Exception as e:
            print(f"⚠️  Не удалось инициализировать LLM клиент: {e}. Рерайт будет недоступен.")
            self.llm_client = None

    async def _notify_admin(self, message: str):
        """Отправляет уведомление администратору при критических ошибках (ТЗ 5.2)."""
        try:
            # Получаем ID администратора из конфигурации или используем первый из whitelist
            admin_id = None
            if hasattr(self.bot, 'admin_id'):
                admin_id = self.bot.admin_id
            else:
                # Получаем из whitelist
                whitelist = sheets_api.get_whitelist()
                if whitelist:
                    admin_id = whitelist[0]  # Первый пользователь из whitelist

            if admin_id:
                await self.bot.send_message(chat_id=admin_id, text=message)
            else:
                print(f"⚠️  Не удалось отправить уведомление администратору: admin_id не найден")
        except Exception as e:
            print(f"⚠️  Ошибка отправки уведомления администратору: {e}")

    def _get_rewrite_prompt(self):
        """Получает промпт для рерайта из Google Sheets (таблица rewrite_prompt)."""
        # Реализуйте чтение из таблицы 'rewrite_prompt'
        data = sheets_api.get_sheet_data("rewrite_prompt")
        # Возвращаем первый непустой промпт
        if len(data) > 1 and len(data[1]) > 0:
            return data[1][0]
        return "Rewrite the following text to make it engaging and persuasive and fit for a social media post."

    def _add_watermark(self, image_url: str, watermark_text: str = "AFFILIATE") -> BytesIO | None:
        """Скачивает изображение, накладывает водяной знак и возвращает BytesIO."""
        try:
            # 1. Загрузка
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content)).convert("RGBA")

            # 2. Наложение текста (Упрощенная реализация)
            txt = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt)
            font = ImageFont.load_default() # Используем дефолтный для минимальных затрат

            # Позиция: нижний правый угол
            text_x = img.width - draw.textlength(watermark_text, font=font) - 10
            text_y = img.height - 20

            draw.text((text_x, text_y), watermark_text, fill=(255, 255, 255, 128), font=font)
            combined = Image.alpha_composite(img, txt)

            # 3. Сохранение в BytesIO
            output = BytesIO()
            combined.convert("RGB").save(output, format="JPEG")
            output.seek(0)
            return output

        except Exception as e:
            print(f"❌ Ошибка при наложении водяного знака: {e}")
            return None

    async def fetch_and_post_enhanced(self, campaign: dict):
        """
        Enhanced posting method with Google Sheets integration.
        Uses content templates, product filters, and automated content generation.
        """
        print(f"DEBUG: fetch_and_post_enhanced called for campaign {campaign.get('name', 'Unknown')}")
        try:
            # Import enhanced services
            from services.content_generator import content_generator
            from services.product_filter import product_filter
            print(f"DEBUG: Enhanced services imported successfully")
        except ImportError as e:
            print(f"⚠️  Enhanced services not available: {e}. Falling back to basic posting.")
            return await self.fetch_and_post(campaign)

        # Get campaign parameters
        params = campaign.get('params', {})
        campaign_id = campaign.get('id')

        # Get enhanced configuration
        content_template_id = params.get('content_template_id')
        product_filter_id = params.get('product_filter_id')
        posting_schedule_id = params.get('posting_schedule_id')

        # --- Product Selection with Filtering ---
        try:
            if product_filter_id:
                # Use filtered products from Google Sheets
                filtered_products = product_filter.get_products_by_filter(product_filter_id)
                if not filtered_products:
                    print(f"⚠️  No products match filter {product_filter_id} for campaign {campaign['name']}")
                    return

                # Select random product from filtered results
                import random
                product_data = random.choice(filtered_products)
                print(f"✅ Selected filtered product: {product_data.get('name', 'Unknown')}")
            else:
                # Fallback to original Amazon API method
                categories = params.get('categories', [])
                subcategories = params.get('subcategories', [])
                min_rating = float(params.get('min_rating', 0.0))

                # Build filters from campaign params
                filters = {}
                if params.get('min_price'):
                    filters['MinPrice'] = params['min_price']
                if params.get('min_saving_percent'):
                    filters['MinSavingPercent'] = params['min_saving_percent']
                if params.get('fulfilled_by_amazon') is not None:
                    filters['FulfilledByAmazon'] = params['fulfilled_by_amazon']

                keywords_parts = []
                if categories:
                    keywords_parts.extend(categories)
                if subcategories:
                    keywords_parts.extend(subcategories)

                keywords = " ".join(keywords_parts) if keywords_parts else "popular product"

                # Use browse_node_ids from campaign params if available (new unified categories system)
                browse_node_ids = params.get('browse_node_ids', [])
                print(f"DEBUG: About to call amazon_paapi_client.search_items with browse_node_ids={browse_node_ids}")
                product_data = await amazon_paapi_client.search_items(
                    keywords=keywords,
                    min_rating=min_rating,
                    filters=filters,
                    browse_node_ids=browse_node_ids if browse_node_ids else None
                )

            if not product_data:
                error_msg = f"No product data available for campaign {campaign['name']}"
                print(f"❌ {error_msg}")
                await self._notify_admin(f"🚨 Error: {error_msg}")
                return

        except Exception as e:
            error_msg = f"Product selection failed for campaign {campaign['name']}: {str(e)}"
            print(f"❌ {error_msg}")
            await self._notify_admin(f"🚨 Error: {error_msg}")
            return

        # --- Content Generation with Templates ---
        try:
            if content_template_id:
                # Use specific template
                content_result = await content_generator.generate_post_content(product_data)
            else:
                # Use category-based template selection
                content_result = await content_generator.generate_post_content(product_data)

            if not content_result:
                print(f"⚠️  Content generation failed, using fallback for campaign {campaign['name']}")
                # Fallback content
                title = product_data.get('Title', 'Amazing Product')
                content_result = {
                    'text': f"✨ **GREAT DEAL!** {title}\n\nCheck out this amazing product!",
                    'hashtags': '#Deal #Product #Affiliate',
                    'product_link': product_data.get('AffiliateLink', ''),
                    'product_image': product_data.get('ImageURL', '')
                }

        except Exception as e:
            error_msg = f"Content generation failed for campaign {campaign['name']}: {str(e)}"
            print(f"❌ {error_msg}")
            await self._notify_admin(f"🚨 Error: {error_msg}")
            return

        # --- UTM Link Generation ---
        affiliate_link = content_result.get('product_link') or product_data.get('AffiliateLink', '')
        if affiliate_link:
            utm_marks = sheets_api.get_utm_marks()
            utm_params = []

            for param, value in utm_marks.items():
                utm_params.append(f"{param}={value}")

            # Add campaign-specific UTM if not present
            if 'utm_campaign' not in utm_marks:
                utm_params.append(f"utm_campaign={campaign['name'].replace(' ', '_')}")

            utm_string = "&".join(utm_params)
            final_link = f"{affiliate_link}{'&' if '?' in affiliate_link else '?'}{utm_string}"
        else:
            final_link = affiliate_link

        # --- Format Final Content ---
        text_content = content_result['text']
        hashtags = content_result.get('hashtags', '')

        # Add affiliate link to content
        if final_link:
            text_content += f"\n\n🔗 [Shop Now]({final_link})"

        if hashtags:
            text_content += f"\n\n{hashtags}"

        # --- Posting with Watermark ---
        image_url = content_result.get('product_image') or product_data.get('ImageURL', '')
        image_stream = self._add_watermark(image_url, watermark_text="AFFILIATE") if image_url else None

        channels = params.get('channels', [])
        successful_posts = 0

        for channel_name in channels:
            try:
                if image_stream:
                    image_stream.seek(0)
                    await self.bot.send_photo(
                        chat_id=channel_name,
                        photo=BufferedInputFile(image_stream.read(), filename="photo.jpg"),
                        caption=text_content,
                        parse_mode='Markdown'
                    )
                else:
                    await self.bot.send_message(
                        chat_id=channel_name,
                        text=text_content,
                        parse_mode='Markdown'
                    )
                successful_posts += 1
                print(f"✅ Posted to {channel_name} for campaign {campaign['name']}")

            except Exception as e:
                print(f"❌ Failed to post to {channel_name}: {e}")

        # --- Statistics Logging ---
        try:
            from services.campaign_manager import campaign_manager

            asin = product_data.get('ASIN', '') or product_data.get('id', '')

            for channel_name in channels:
                await campaign_manager.log_post_statistics({
                    'campaign_id': campaign_id,
                    'channel_name': channel_name,
                    'asin': asin,
                    'final_link': final_link
                })

            print(f"✅ Statistics logged for {successful_posts} posts in campaign {campaign['name']}")

        except Exception as e:
            print(f"⚠️  Statistics logging failed: {e}")

    async def fetch_and_post(self, campaign: dict):
        """Legacy posting method for backward compatibility."""
        return await self.fetch_and_post_enhanced(campaign)
