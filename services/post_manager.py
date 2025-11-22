# services/post_manager.py
import requests
from aiogram.types import BufferedInputFile, InputMediaPhoto
from PIL import Image, ImageDraw, ImageFont # Для водяных знаков
from io import BytesIO
from services.sheets_api import sheets_api
from services.amazon_paapi_client import amazon_paapi_client
from services.llm_client import OpenAIClient
from typing import Optional


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

    async def _notify_user(self, message: str, user_id: Optional[int] = None, campaign_id: Optional[int] = None):
        """Отправляет уведомление целевому пользователю или администратору в качестве фолбэка."""
        target_id = user_id

        # If no user_id provided, try to get campaign creator
        if not target_id and campaign_id:
            try:
                from services.campaign_manager import get_campaign_manager
                campaign_mgr = get_campaign_manager()
                if campaign_mgr:
                    campaign_details = await campaign_mgr.get_campaign_details_full(campaign_id)
                    if campaign_details and campaign_details.get('created_by_user_id'):
                        target_id = campaign_details['created_by_user_id']
            except Exception as e:
                print(f"⚠️  Не удалось получить создателя кампании {campaign_id}: {e}")

        if not target_id:
            try:
                # Фолбэк: получаем ID администратора из конфигурации или используем первый из whitelist
                if hasattr(self.bot, 'admin_id'):
                    target_id = self.bot.admin_id
                else:
                    whitelist = sheets_api.get_whitelist()
                    if whitelist:
                        target_id = whitelist[0]  # Первый пользователь из whitelist
            except Exception as e:
                print(f"⚠️  Не удалось получить ID администратора для фолбэк-уведомления: {e}")
                return

        if target_id:
            try:
                await self.bot.send_message(chat_id=target_id, text=message)
            except Exception as e:
                print(f"⚠️  Ошибка отправки уведомления пользователю {target_id}: {e}")
        else:
            print(f"⚠️  Не удалось отправить уведомление: ID получателя не найден.")

    def _get_rewrite_prompt(self):
        """Получает промпт для рерайта из Google Sheets (таблица rewrite_prompt)."""
        # Реализуйте чтение из таблицы 'rewrite_prompt'
        data = sheets_api.get_sheet_data("rewrite_prompt")
        # Возвращаем первый непустой промпт
        if len(data) > 1 and len(data[1]) > 0:
            return data[1][0]
        return "Rewrite the following text to make it engaging and persuasive and fit for a social media post."

    def _add_watermark(self, image_url: str, channel_name: str) -> BytesIO | None:
        """Скачивает изображение, накладывает профессиональный водяной знак с названием канала и возвращает BytesIO."""
        try:
            # 1. Загрузка изображения
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content)).convert("RGBA")

            # 2. Создание слоя для водяного знака
            watermark_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)

            # 3. Настройка шрифта
            font_size = max(24, min(img.width, img.height) // 25)  # Увеличен минимальный размер
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()

            # 4. Расчет размеров текста
            text_bbox = draw.textbbox((0, 0), channel_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # 5. Создание стильного фона для текста (полупрозрачный черный с закруглением)
            padding = 16
            bg_x1 = img.width - text_width - padding * 3
            bg_y1 = img.height - text_height - padding * 2
            bg_x2 = img.width - padding
            bg_y2 = img.height - padding

            # Рисуем закругленный прямоугольник с градиентом
            from PIL import ImageDraw
            draw.rounded_rectangle(
                [(bg_x1, bg_y1), (bg_x2, bg_y2)],
                radius=12,  # Закругленные углы
                fill=(0, 0, 0, 140)  # Полупрозрачный черный фон
            )

            # Добавляем легкую тень/обводку для лучшей видимости
            shadow_offset = 2
            for offset_x, offset_y in [(-shadow_offset, -shadow_offset), (-shadow_offset, shadow_offset),
                                     (shadow_offset, -shadow_offset), (shadow_offset, shadow_offset)]:
                draw.text(
                    (bg_x1 + padding + offset_x, bg_y1 + padding + offset_y),
                    channel_name,
                    fill=(0, 0, 0, 80),
                    font=font
                )

            # 6. Рисуем основной текст белым цветом
            text_x = bg_x1 + padding
            text_y = bg_y1 + padding
            draw.text((text_x, text_y), channel_name, fill=(255, 255, 255, 255), font=font)

            # 7. Добавляем тонкий белый бордер для выделения
            for offset_x, offset_y in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text(
                    (text_x + offset_x, text_y + offset_y),
                    channel_name,
                    fill=(255, 255, 255, 60),
                    font=font
                )

            # 8. Объединяем изображение с водяным знаком
            combined = Image.alpha_composite(img, watermark_layer)

            # 9. Сохранение в BytesIO с оптимизацией
            output = BytesIO()
            combined.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
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
        print(f"DEBUG: Campaign object keys: {list(campaign.keys())}")
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
        language = params.get('language', 'en')
        user_id = params.get('created_by_user_id')

        # Get enhanced configuration
        content_template_id = params.get('content_template_id')
        product_filter_id = params.get('product_filter_id')
        posting_schedule_id = params.get('posting_schedule_id')

        print(f"DEBUG: campaign_id = {campaign_id}, params keys = {list(params.keys())}")

        # --- Product Selection with Filtering ---
        try:
            print(f"DEBUG: Starting product selection logic")
            print(f"DEBUG: product_filter_id = '{product_filter_id}', content_template_id = '{content_template_id}'")
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
                if params.get('fulfilled_by_amazon') is not None:
                    filters['FulfilledByAmazon'] = params['fulfilled_by_amazon']

                keywords_parts = []
                if categories:
                    keywords_parts.extend(categories)
                if subcategories:
                    keywords_parts.extend(subcategories)

                # Use dict.fromkeys to get unique keywords while preserving order
                unique_keywords = list(dict.fromkeys(keywords_parts))
                keywords = " ".join(unique_keywords) if unique_keywords else "popular product"

                # Use browse_node_ids from campaign params if available (new unified categories system)
                browse_node_ids = params.get('browse_node_ids', [])
                print(f"DEBUG: Campaign params: {params}")
                print(f"DEBUG: About to call amazon_paapi_client.search_items with browse_node_ids={browse_node_ids}")

                # Get already posted ASINs for this campaign to prevent duplicates
                print(f"DEBUG: About to get campaign_manager instance")
                from services.campaign_manager import get_campaign_manager
                campaign_manager_instance = get_campaign_manager()
                print(f"DEBUG: Campaign manager instance retrieved: {campaign_manager_instance}")
                try:
                    posted_asins = await campaign_manager_instance.get_posted_asins(campaign_id, limit=1000)
                    print(f"DEBUG: Campaign {campaign['name']} has {len(posted_asins)} already posted products")
                except Exception as e:
                    print(f"DEBUG: Error getting posted ASINs: {e}")
                    posted_asins = []

                # Try to find a new product using enhanced search that returns multiple products
                product_data = None

                # First, try enhanced search to get multiple products and pick one not posted
                print(f"DEBUG: browse_node_ids = {browse_node_ids}, type = {type(browse_node_ids)}")
                if browse_node_ids:
                    print(f"DEBUG: Trying enhanced search for multiple products in browse nodes {browse_node_ids}")
                    try:
                        multiple_products = await amazon_paapi_client.search_items_enhanced(
                            browse_node_ids=browse_node_ids,
                            min_rating=min_rating,
                            min_price=params.get('min_price'),
                            fulfilled_by_amazon=params.get('fulfilled_by_amazon'),
                            max_sales_rank=params.get('max_sales_rank'),
                            max_results=20  # Get up to 20 products for variety
                        )
                        print(f"DEBUG: Enhanced search completed without exception")
                    except Exception as e:
                        print(f"DEBUG: Enhanced search threw exception: {e}")
                        multiple_products = None

                    # Truncate log to first 100 chars to reduce verbosity
                    products_str = str(multiple_products)
                    truncated = products_str[:100] + "..." if len(products_str) > 100 else products_str
                    print(f"DEBUG: Enhanced search returned: {truncated}")

                    if multiple_products and len(multiple_products) > 0:
                        print(f"DEBUG: Found {len(multiple_products)} candidate products")

                        # Filter out already posted products
                        available_products = []
                        for product in multiple_products:
                            product_asin = product.get('asin', '')
                            if product_asin and product_asin not in posted_asins:
                                available_products.append(product)
                            else:
                                print(f"DEBUG: Filtering out already posted ASIN: {product_asin}")

                        print(f"DEBUG: {len(available_products)} products available after filtering")

                        if available_products:
                            # Filter for quality products with essential data (price + title)
                            quality_products = []
                            for product in available_products:
                                # Check if product has essential data: price and title
                                has_price = product.get('price') is not None and product.get('price') > 0
                                has_title = product.get('title') and product.get('title').strip()

                                # Optional data (nice to have but not required)
                                has_rating = product.get('rating') is not None and product.get('rating') > 0
                                has_sales_rank = product.get('sales_rank') is not None and product.get('sales_rank') > 0
                                has_features = (product.get('features') and
                                              isinstance(product.get('features'), list) and
                                              len(product.get('features', [])) > 0)

                                if has_price and has_title:
                                    quality_products.append(product)
                                    print(f"DEBUG: Quality product found: {product.get('title', 'Unknown')} (ASIN: {product.get('asin')}) - Price: €{product.get('price')}, Rating: {has_rating}, Rank: {has_sales_rank}, Features: {has_features}")
                                else:
                                    print(f"DEBUG: Skipping incomplete product: {product.get('title', 'Unknown')} (ASIN: {product.get('asin')}) - Price: {has_price}, Title: {bool(has_title)}")

                            if quality_products:
                                # Pick a random quality product
                                import random
                                selected_product = random.choice(quality_products)
                                print(f"DEBUG: Selected quality product: {selected_product.get('title', 'Unknown')} (ASIN: {selected_product.get('asin')})")
                                if selected_product.get('discount_percent'):
                                    print(f"DEBUG: Product discount: {selected_product.get('discount_percent')}%")

                                # Convert to the format expected by the rest of the system
                                product_data = {
                                    'ASIN': selected_product.get('asin', ''),
                                    'Title': selected_product.get('title', ''),
                                    'ImageURLs': selected_product.get('image_urls', []),
                                    'AffiliateLink': selected_product.get('affiliate_link', ''),
                                    'Price': f"€{selected_product.get('price', 0):.2f}" if selected_product.get('price') else '',
                                    'Rating': str(selected_product.get('rating', '')),
                                    'ReviewsCount': str(selected_product.get('review_count', '')),
                                    'SalesRank': str(selected_product.get('sales_rank', '')),
                                    'features': selected_product.get('features', [])
                                }
                                print(f"DEBUG: Successfully selected quality product from enhanced search")
                            else:
                                print(f"DEBUG: No quality products found with complete data")
                                product_data = None
                        else:
                            print(f"DEBUG: No products available after filtering posted ASINs")
                    else:
                        print(f"DEBUG: Enhanced search returned no products")

                # Fallback to original method if enhanced search didn't work
                if not product_data:
                    print(f"DEBUG: Falling back to original search method")
                    max_attempts = 3  # Try fewer times with original method

                    for attempt in range(max_attempts):
                        candidate_product = await amazon_paapi_client.search_items(
                            keywords=keywords,
                            min_rating=min_rating,
                            filters=filters,
                            browse_node_ids=browse_node_ids if browse_node_ids else None,
                            exclude_asins=posted_asins
                        )

                        if candidate_product:
                            candidate_asin = candidate_product.get('ASIN') or candidate_product.get('asin', '')
                            if candidate_asin and candidate_asin not in posted_asins:
                                product_data = candidate_product
                                print(f"DEBUG: Found new product (ASIN: {candidate_asin}) on attempt {attempt + 1}")
                                break
                            else:
                                print(f"DEBUG: Product ASIN {candidate_asin} already posted or excluded")

                if not product_data:
                    print(f"WARNING: Could not find a new product for campaign {campaign['name']}")
                    # DO NOT allow reposting - skip this posting cycle instead
                    # The product discovery cycle should refill the queue
                    error_msg = f"Не удалось найти новый продукт для кампании '{campaign['name']}'. Очередь может быть пуста - ожидание цикла обнаружения продуктов."
                    print(f"⏭️  {error_msg}")
                    # Optionally notify admin if queue is consistently empty
                    queue_size = await campaign_manager_instance.get_queue_size(campaign_id)
                    if queue_size == 0:
                        await self._notify_user(
                            f"⚠️ Очередь кампании '{campaign['name']}' пуста. Цикл обнаружения продуктов скоро ее пополнит.",
                            user_id=user_id
                        )
                    return  # Skip posting instead of reposting

            if not product_data:
                error_msg = f"Нет данных о продукте для кампании {campaign['name']}"
                print(f"❌ {error_msg}")
                await self._notify_user(f"🚨 Ошибка: {error_msg}", user_id=user_id)
                return

        except Exception as e:
            error_msg = f"Выбор продукта для кампании {campaign['name']} не удался: {str(e)}"
            print(f"❌ {error_msg}")
            await self._notify_user(f"🚨 Ошибка: {error_msg}", user_id=user_id)
            return

        # --- Content Generation with Templates ---
        try:
            # Get category from campaign (use first category if multiple exist)
            campaign_categories = params.get('categories', [])
            category = None
            if campaign_categories and isinstance(campaign_categories, list) and len(campaign_categories) > 0:
                # Use first category from campaign
                category = campaign_categories[0]

            if content_template_id:
                # Use specific template
                content_result = await content_generator.generate_post_content(product_data, language=language, category=category)
            else:
                # Use category-based template selection
                content_result = await content_generator.generate_post_content(product_data, language=language, category=category)

            # Convert to post content format if needed
            if content_result and not isinstance(content_result, dict):
                content_result = {
                    'text': content_result.get('content', ''),
                    'hashtags': content_result.get('hashtags', '#Product #Affiliate'),
                    'product_link': product_data.get('AffiliateLink', ''),
                    'product_images': product_data.get('ImageURLs', [])
                }

            if not content_result:
                print(f"⚠️  Content generation failed, using fallback for campaign {campaign['name']}")
                # Enhanced fallback content with available product data
                title = product_data.get('Title', 'Amazing Product')
                rating = product_data.get('Rating', '')
                reviews = product_data.get('ReviewsCount', '')
                price = product_data.get('Price', '')

                # Build enhanced fallback text
                text_parts = [f"✨ **GREAT DEAL!** {title}"]

                if rating and rating != 'None':
                    text_parts.append(f"⭐ **{rating}/5 stars**")
                if reviews and reviews != 'None':
                    text_parts.append(f"📊 **{reviews} reviews**")
                if price and price != 'None':
                    text_parts.append(f"💰 **Price: {price}**")

                text_parts.append("\nCheck out this amazing product!")

                content_result = {
                    'text': '\n'.join(text_parts),
                    'hashtags': '#Deal #Product #Affiliate',
                    'product_link': product_data.get('AffiliateLink', ''),
                    'product_images': product_data.get('ImageURLs', [])
                }

        except Exception as e:
            error_msg = f"Генерация контента для кампании {campaign['name']} не удалась: {str(e)}"
            print(f"❌ {error_msg}")
            await self._notify_user(f"🚨 Ошибка: {error_msg}", user_id=user_id)
            return

        # Get base affiliate link and UTM marks
        base_affiliate_link = content_result.get('product_link') or product_data.get('AffiliateLink', '')
        utm_marks = sheets_api.get_utm_marks()
        channel_tracking_ids = sheets_api.get_channel_tracking_ids()

        # --- Format Final Content ---
        base_text_content = content_result['text']

        # --- Posting with Watermark ---
        image_urls = content_result.get('product_images') or product_data.get('ImageURLs', [])
        channels = params.get('channels', [])
        successful_posts = 0

        for channel_name in channels:
            # Create channel-specific UTM link
            if base_affiliate_link:
                utm_params = []

                # Add channel-specific track ID, fallback to campaign track_id
                channel_track_id = channel_tracking_ids.get(channel_name)
                if channel_track_id:
                    utm_params.append(f"tag={channel_track_id}")
                    print(f"✅ Added channel Track ID for {channel_name}: {channel_track_id}")
                else:
                    # Fallback to campaign track_id
                    campaign_track_id = campaign.get('track_id')
                    if campaign_track_id:
                        utm_params.append(f"tag={campaign_track_id}")
                        print(f"✅ Added campaign Track ID (fallback) for {channel_name}: {campaign_track_id}")

                for param, value in utm_marks.items():
                    utm_params.append(f"{param}={value}")

                # Add campaign-specific UTM if not present
                if 'utm_campaign' not in utm_marks:
                    utm_params.append(f"utm_campaign={campaign['name'].replace(' ', '_')}")

                utm_string = "&".join(utm_params)
                final_link = f"{base_affiliate_link}{'&' if '?' in base_affiliate_link else '?'}{utm_string}"
            else:
                final_link = base_affiliate_link

            # Create channel-specific text content
            text_content = base_text_content
            if final_link:
                text_content += f"\n\n🔗 [Shop Now]({final_link})"

            # Truncate content to Telegram's caption limit (1024 chars)
            if len(text_content) > 1024:
                text_content = text_content[:1020] + "..."
            try:
                if not image_urls:
                    # No images, send text only
                    await self.bot.send_message(
                        chat_id=channel_name,
                        text=text_content,
                        parse_mode='Markdown'
                    )
                elif len(image_urls) == 1:
                    # Single image, use send_photo
                    image_stream = self._add_watermark(image_urls[0], channel_name)
                    if image_stream:
                        image_stream.seek(0)
                        await self.bot.send_photo(
                            chat_id=channel_name,
                            photo=BufferedInputFile(image_stream.read(), filename="photo.jpg"),
                            caption=text_content,
                            parse_mode='Markdown'
                        )
                else:
                    # Multiple images, use send_media_group
                    media_group = []
                    for i, url in enumerate(image_urls):
                        image_stream = self._add_watermark(url, channel_name)
                        if image_stream:
                            image_stream.seek(0)
                            photo_file = BufferedInputFile(image_stream.read(), filename=f"photo{i}.jpg")
                            # Add caption only to the first photo
                            caption = text_content if i == 0 else None
                            parse_mode = 'Markdown' if i == 0 else None
                            media_group.append(InputMediaPhoto(media=photo_file, caption=caption, parse_mode=parse_mode))
                    
                    if media_group:
                        await self.bot.send_media_group(chat_id=channel_name, media=media_group)

                successful_posts += 1
                print(f"✅ Posted to {channel_name} for campaign {campaign['name']}")

            except Exception as e:
                error_msg = f"❌ Не удалось опубликовать в {channel_name} для кампании '{campaign['name']}': {e}"
                print(error_msg)
                await self._notify_user(f"🚨 Ошибка постинга: {error_msg}", user_id=user_id)

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

    async def post_queued_product(self, campaign: dict, product_data: dict):
        """
        Post a pre-fetched product from the queue without API calls.
        Used by the product queue system for faster, more reliable posting.
        """
        print(f"📦 Posting queued product: {product_data.get('asin', 'Unknown')} - {product_data.get('title', 'Unknown')[:50]}...")

        # Quality check: ensure product has essential data (price + title) before posting
        has_price = product_data.get('price') is not None and product_data.get('price') > 0
        has_title = product_data.get('title') and product_data.get('title').strip()

        if not (has_price and has_title):
            print(f"⚠️  Skipping queued product {product_data.get('asin')} - missing essential data: Price: {has_price}, Title: {bool(has_title)}")
            return

        print(f"✅ Quality check passed for queued product {product_data.get('asin')}")

        try:
            # Import enhanced services
            from services.content_generator import content_generator
            from services.sheets_api import sheets_api
        except ImportError as e:
            print(f"⚠️  Enhanced services not available for queued product posting")
            return

        campaign_id = campaign.get('id')
        params = campaign.get('params', {})
        language = params.get('language', 'en')
        user_id = params.get('created_by_user_id')

        # Use enriched product data directly - content generator now handles multiple formats
        formatted_product_data = {
            'asin': product_data.get('asin', ''),
            'title': product_data.get('title', ''),
            'image_urls': product_data.get('image_urls', []),
            'affiliate_link': product_data.get('affiliate_link', ''),
            'price': product_data.get('price'),  # Keep as numeric for better formatting
            'rating': product_data.get('rating'),  # Keep as numeric for better formatting
            'review_count': product_data.get('review_count'),  # Keep as numeric for better formatting
            'sales_rank': product_data.get('sales_rank'),  # Keep as numeric for better formatting
            'description': product_data.get('description', ''),
            'features': product_data.get('features', [])
        }

        # --- Content Generation ---
        try:
            content_result = await content_generator.generate_post_content(formatted_product_data, language=language)

            # Convert to post content format if needed
            if content_result and not isinstance(content_result, dict):
                content_result = {
                    'text': content_result.get('content', ''),
                    'hashtags': content_result.get('hashtags', '#Product #Affiliate'),
                    'product_link': formatted_product_data.get('affiliate_link', ''),
                    'product_images': formatted_product_data.get('image_urls', [])
                }

            if not content_result:
                print(f"⚠️  Content generation failed for queued product, using fallback")
                # Enhanced fallback content with available product data
                title = formatted_product_data.get('Title', 'Amazing Product')
                rating = formatted_product_data.get('Rating', '')
                reviews = formatted_product_data.get('ReviewsCount', '')
                price = formatted_product_data.get('Price', '')

                # Build enhanced fallback text
                text_parts = [f"✨ **GREAT DEAL!** {title}"]

                if rating and rating != 'None' and rating != '':
                    text_parts.append(f"⭐ **{rating}/5 stars**")
                if reviews and reviews != 'None' and reviews != '':
                    text_parts.append(f"📊 **{reviews} reviews**")
                if price and price != 'None' and price != '':
                    text_parts.append(f"💰 **Price: {price}**")

                text_parts.append("\nCheck out this amazing product!")

                content_result = {
                    'text': '\n'.join(text_parts),
                    'hashtags': '#Deal #Product #Affiliate',
                    'product_link': formatted_product_data.get('affiliate_link', ''),
                    'product_images': formatted_product_data.get('image_urls', [])
                }

        except Exception as e:
            error_msg = f"Генерация контента для продукта из очереди {product_data.get('asin')} не удалась: {str(e)}"
            print(f"❌ {error_msg}")
            await self._notify_user(f"🚨 Ошибка: {error_msg}", user_id=user_id)
            return

        # Get base affiliate link and UTM marks
        base_affiliate_link = content_result.get('product_link') or formatted_product_data.get('affiliate_link', '')
        utm_marks = sheets_api.get_utm_marks()
        channel_tracking_ids = sheets_api.get_channel_tracking_ids()

        # --- Format Final Content ---
        base_text_content = content_result['text']

        # --- Posting with Watermark ---
        image_urls = content_result.get('product_images') or formatted_product_data.get('image_urls', [])
        channels = params.get('channels', [])
        successful_posts = 0

        # Store channel-specific links for statistics logging
        channel_links = {}

        for channel_name in channels:
            # Create channel-specific UTM link
            if base_affiliate_link:
                utm_params = []

                # Add channel-specific track ID, fallback to campaign track_id
                channel_track_id = channel_tracking_ids.get(channel_name)
                if channel_track_id:
                    utm_params.append(f"tag={channel_track_id}")
                    print(f"✅ Added channel Track ID for {channel_name}: {channel_track_id}")
                else:
                    # Fallback to campaign track_id
                    campaign_track_id = campaign.get('track_id')
                    if campaign_track_id:
                        utm_params.append(f"tag={campaign_track_id}")
                        print(f"✅ Added campaign Track ID (fallback) for {channel_name}: {campaign_track_id}")

                for param, value in utm_marks.items():
                    utm_params.append(f"{param}={value}")

                # Add campaign-specific UTM if not present
                if 'utm_campaign' not in utm_marks:
                    utm_params.append(f"utm_campaign={campaign['name'].replace(' ', '_')}")

                utm_string = "&".join(utm_params)
                final_link = f"{base_affiliate_link}{'&' if '?' in base_affiliate_link else '?'}{utm_string}"
            else:
                final_link = base_affiliate_link

            # Store channel-specific link for stats logging
            channel_links[channel_name] = final_link

            # Create channel-specific text content
            text_content = base_text_content
            if final_link:
                text_content += f"\n\n🔗 [Shop Now]({final_link})"

            # Truncate content to Telegram's caption limit (1024 chars)
            if len(text_content) > 1024:
                text_content = text_content[:1020] + "..."
            try:
                if not image_urls:
                    # No images, send text only
                    await self.bot.send_message(
                        chat_id=channel_name,
                        text=text_content,
                        parse_mode='Markdown'
                    )
                elif len(image_urls) == 1:
                    # Single image, use send_photo
                    image_stream = self._add_watermark(image_urls[0], channel_name)
                    if image_stream:
                        image_stream.seek(0)
                        await self.bot.send_photo(
                            chat_id=channel_name,
                            photo=BufferedInputFile(image_stream.read(), filename="photo.jpg"),
                            caption=text_content,
                            parse_mode='Markdown'
                        )
                else:
                    # Multiple images, use send_media_group
                    media_group = []
                    for i, url in enumerate(image_urls):
                        image_stream = self._add_watermark(url, channel_name)
                        if image_stream:
                            image_stream.seek(0)
                            photo_file = BufferedInputFile(image_stream.read(), filename=f"photo{i}.jpg")
                            # Add caption only to the first photo
                            caption = text_content if i == 0 else None
                            parse_mode = 'Markdown' if i == 0 else None
                            media_group.append(InputMediaPhoto(media=photo_file, caption=caption, parse_mode=parse_mode))

                    if media_group:
                        await self.bot.send_media_group(chat_id=channel_name, media=media_group)

                successful_posts += 1
                print(f"✅ Posted queued product to {channel_name} for campaign {campaign['name']}")

            except Exception as e:
                error_msg = f"❌ Не удалось опубликовать продукт из очереди в {channel_name} для кампании '{campaign['name']}': {e}"
                print(error_msg)
                await self._notify_user(f"🚨 Ошибка постинга (очередь): {error_msg}", user_id=user_id)

        # --- Statistics Logging ---
        try:
            from services.campaign_manager import campaign_manager

            asin = formatted_product_data.get('ASIN', '')

            for channel_name in channels:
                await campaign_manager.log_post_statistics({
                    'campaign_id': campaign_id,
                    'channel_name': channel_name,
                    'asin': asin,
                    'final_link': final_link
                })

            print(f"✅ Statistics logged for {successful_posts} posts of queued product in campaign {campaign['name']}")

        except Exception as e:
            print(f"⚠️  Statistics logging failed for queued product: {e}")

    async def fetch_and_post(self, campaign: dict):
        """Legacy posting method for backward compatibility."""
        return await self.fetch_and_post_enhanced(campaign)
