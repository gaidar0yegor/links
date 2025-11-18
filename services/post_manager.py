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

    def _add_watermark(self, image_url: str, channel_name: str) -> BytesIO | None:
        """Скачивает изображение, накладывает водяной знак с названием канала и возвращает BytesIO."""
        try:
            # 1. Загрузка
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content)).convert("RGBA")

            # 2. Наложение текста (Улучшенная реализация с большим шрифтом)
            txt = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt)

            # Используем больший шрифт (масштабируемый по размеру изображения)
            font_size = max(20, min(img.width, img.height) // 30)  # Минимум 20px, масштабируется
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                # Fallback to default if truetype not available
                font = ImageFont.load_default()

            # Позиция: нижний правый угол с отступом
            text_bbox = draw.textbbox((0, 0), channel_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            text_x = img.width - text_width - 20
            text_y = img.height - text_height - 20

            # Полупрозрачный белый текст с черной обводкой для лучшей видимости
            # Сначала рисуем черную обводку
            for offset_x, offset_y in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text((text_x + offset_x, text_y + offset_y), channel_name, fill=(0, 0, 0, 180), font=font)

            # Затем белый текст
            draw.text((text_x, text_y), channel_name, fill=(255, 255, 255, 220), font=font)

            combined = Image.alpha_composite(img, txt)

            # 3. Сохранение в BytesIO
            output = BytesIO()
            combined.convert("RGB").save(output, format="JPEG", quality=95)
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
                            min_saving_percent=params.get('min_saving_percent'),
                            fulfilled_by_amazon=params.get('fulfilled_by_amazon'),
                            max_results=20  # Get up to 20 products for variety
                        )
                        print(f"DEBUG: Enhanced search completed without exception")
                    except Exception as e:
                        print(f"DEBUG: Enhanced search threw exception: {e}")
                        multiple_products = None

                    print(f"DEBUG: Enhanced search returned: {multiple_products}")

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

                                # Convert to the format expected by the rest of the system
                                product_data = {
                                    'ASIN': selected_product.get('asin', ''),
                                    'Title': selected_product.get('title', ''),
                                    'ImageURL': selected_product.get('image_url', ''),
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
                            browse_node_ids=browse_node_ids if browse_node_ids else None
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
                    # As a last resort, allow reposting if no new products available
                    # This prevents campaigns from going silent
                    fallback_product = await amazon_paapi_client.search_items(
                        keywords=keywords,
                        min_rating=min_rating,
                        filters=filters,
                        browse_node_ids=browse_node_ids if browse_node_ids else None
                    )
                    if fallback_product:
                        product_data = fallback_product
                        print(f"DEBUG: Using fallback product (may be repost): {fallback_product.get('Title', 'Unknown')}")

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
                content_result = await content_generator.generate_post_content(product_data, language=language)
            else:
                # Use category-based template selection
                content_result = await content_generator.generate_post_content(product_data, language=language)

            # Convert to post content format if needed
            if content_result and not isinstance(content_result, dict):
                content_result = {
                    'text': content_result.get('content', ''),
                    'hashtags': content_result.get('hashtags', '#Product #Affiliate'),
                    'product_link': product_data.get('AffiliateLink', ''),
                    'product_image': product_data.get('ImageURL', '')
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
        features = content_result.get('features', [])

        # Add features as bullet points
        if features:
            feature_bullets = "\n\n" + "\n".join(f"• {feature.strip()}" for feature in features[:3])
            text_content += feature_bullets

        # Add affiliate link to content
        if final_link:
            text_content += f"\n\n🔗 [Shop Now]({final_link})"

        if hashtags:
            text_content += f"\n\n{hashtags}"

        # --- Posting with Watermark ---
        # Truncate content to Telegram's caption limit (1024 chars)
        if len(text_content) > 1024:
            text_content = text_content[:1020] + "..."

        image_url = content_result.get('product_image') or product_data.get('ImageURL', '')
        channels = params.get('channels', [])
        successful_posts = 0

        for channel_name in channels:
            # Create watermark with channel name for each channel
            image_stream = self._add_watermark(image_url, channel_name) if image_url else None
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

        # Use enriched product data directly - content generator now handles multiple formats
        formatted_product_data = {
            'asin': product_data.get('asin', ''),
            'title': product_data.get('title', ''),
            'image_url': product_data.get('image_url', ''),
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
                    'product_link': formatted_product_data.get('AffiliateLink', ''),
                    'product_image': formatted_product_data.get('ImageURL', '')
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
                    'product_link': formatted_product_data.get('AffiliateLink', ''),
                    'product_image': formatted_product_data.get('ImageURL', '')
                }

        except Exception as e:
            error_msg = f"Content generation failed for queued product {product_data.get('asin')}: {str(e)}"
            print(f"❌ {error_msg}")
            await self._notify_admin(f"🚨 Error: {error_msg}")
            return

        # --- UTM Link Generation ---
        affiliate_link = content_result.get('product_link') or formatted_product_data.get('AffiliateLink', '')
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
        features = content_result.get('features', [])

        # Add features as bullet points
        if features:
            feature_bullets = "\n\n" + "\n".join(f"• {feature.strip()}" for feature in features[:3])
            text_content += feature_bullets

        # Add affiliate link to content
        if final_link:
            text_content += f"\n\n🔗 [Shop Now]({final_link})"

        if hashtags:
            text_content += f"\n\n{hashtags}"

        # --- Posting with Watermark ---
        # Truncate content to Telegram's caption limit (1024 chars)
        if len(text_content) > 1024:
            text_content = text_content[:1020] + "..."

        image_url = content_result.get('product_image') or formatted_product_data.get('ImageURL', '')
        channels = params.get('channels', [])
        successful_posts = 0

        for channel_name in channels:
            # Create watermark with channel name for each channel
            image_stream = self._add_watermark(image_url, channel_name) if image_url else None
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
                print(f"✅ Posted queued product to {channel_name} for campaign {campaign['name']}")

            except Exception as e:
                print(f"❌ Failed to post queued product to {channel_name}: {e}")

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
