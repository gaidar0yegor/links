# services/post_manager.py
import requests
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from aiogram.types import BufferedInputFile, InputMediaPhoto
# PIL imports removed - watermark functionality disabled
from io import BytesIO
from services.sheets_api import sheets_api
from services.amazon_paapi_client import amazon_paapi_client
from services.llm_client import OpenAIClient
from typing import Optional


def replace_affiliate_tag(url: str, new_tag: str) -> str:
    """
    Заменяет существующий tag= параметр в Amazon affiliate ссылке на новый.
    Если tag= отсутствует, добавляет его.
    
    Args:
        url: Исходная affiliate ссылка
        new_tag: Новый track ID для замены
    
    Returns:
        URL с замененным tag параметром
    """
    if not url or not new_tag:
        return url
    
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Заменяем или добавляем tag
    query_params['tag'] = [new_tag]
    
    # Собираем URL обратно
    # Используем urlencode с doseq=True для корректной обработки списков
    new_query = urlencode({k: v[0] if len(v) == 1 else v for k, v in query_params.items()}, doseq=True)
    
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return new_url


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
        """Отправляет уведомление пользователям с включенными уведомлениями (whitelist -> notification=Yes)."""
        
        # 1. Получаем список пользователей для уведомлений из Google Sheets
        target_ids = sheets_api.get_users_for_notification()

        # 2. Если список пуст, используем фолбэк (создатель кампании или админ)
        if not target_ids:
            if user_id:
                target_ids = [user_id]
            elif campaign_id:
                try:
                    from services.campaign_manager import get_campaign_manager
                    campaign_mgr = get_campaign_manager()
                    if campaign_mgr:
                        campaign_details = await campaign_mgr.get_campaign_details_full(campaign_id)
                        if campaign_details and campaign_details.get('created_by_user_id'):
                            target_ids = [campaign_details['created_by_user_id']]
                except Exception as e:
                    print(f"⚠️  Не удалось получить создателя кампании {campaign_id}: {e}")
            
            # Если все еще пусто, пробуем админа
            if not target_ids:
                 if hasattr(self.bot, 'admin_id'):
                    target_ids = [self.bot.admin_id]
                 else:
                    # Fallback to first whitelist user if available
                    whitelist = sheets_api.get_whitelist()
                    if whitelist:
                        target_ids = [whitelist[0]]

        if not target_ids:
            print(f"⚠️ Некому отправлять уведомление: {message}")
            return

        # 3. Отправляем сообщение всем получателям
        for target_id in set(target_ids): # Use set to avoid duplicates
            try:
                await self.bot.send_message(chat_id=target_id, text=message)
            except Exception as e:
                print(f"⚠️ Ошибка отправки уведомления пользователю {target_id}: {e}")

    def _get_rewrite_prompt(self):
        """Получает промпт для рерайта из Google Sheets (таблица rewrite_prompt)."""
        # Реализуйте чтение из таблицы 'rewrite_prompt'
        data = sheets_api.get_sheet_data("rewrite_prompt")
        # Возвращаем первый непустой промпт
        if len(data) > 1 and len(data[1]) > 0:
            return data[1][0]
        return "Rewrite the following text to make it engaging and persuasive and fit for a social media post."

    def _download_image(self, image_url: str) -> BytesIO | None:
        """Скачивает изображение и возвращает BytesIO."""
        try:
            response = requests.get(image_url, timeout=10)
            output = BytesIO(response.content)
            output.seek(0)
            return output
        except Exception as e:
            print(f"❌ Ошибка при загрузке изображения: {e}")
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
                            min_review_count=params.get('min_review_count', 0),
                            max_results=5  # Reduced from 20 to 5 for emergency post to save resources
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

                                                                # Check review count
                                min_reviews = params.get('min_review_count', 0)
                                has_enough_reviews = True
                                if min_reviews > 0:
                                    review_count = product.get('review_count')
                                    if review_count is None or int(review_count) < min_reviews:
                                        has_enough_reviews = False

                                if has_price and has_title and has_enough_reviews:
                                    quality_products.append(product)
                                    print(f"DEBUG: Quality product found: {product.get('title', 'Unknown')} (ASIN: {product.get('asin')}) - Price: €{product.get('price')}, Rating: {has_rating}, Rank: {has_sales_rank}, Features: {has_features}")
                                else:
                                    print(f"DEBUG: Skipping incomplete product: {product.get('title', 'Unknown')} (ASIN: {product.get('asin')}) - Price: {has_price}, Title: {bool(has_title)}, Reviews: {has_enough_reviews}")

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
                            
                            # Check review count for fallback product
                            min_reviews = params.get('min_review_count', 0)
                            reviews_count = candidate_product.get('ReviewsCount') or candidate_product.get('review_count', 0)
                            try:
                                reviews_count = int(reviews_count)
                            except (ValueError, TypeError):
                                reviews_count = 0
                                
                            if min_reviews > 0 and reviews_count < min_reviews:
                                print(f"DEBUG: Fallback product {candidate_asin} skipped: reviews {reviews_count} < min {min_reviews}")
                                continue

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
                            f"⚠️ Очередь кампании '{campaign['name']}' пуста. Новые товары еще не были обнаружены. При повторной ошибке, стоит ослабить фильтры или перезапустить кампанию.",
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
                error_msg = f"Генерация контента не удалась (LLM Error), пропускаем пост для кампании {campaign['name']}"
                print(f"⚠️  {error_msg}")
                # Notify user about the failure instead of posting bad content
                await self._notify_user(f"🚨 Пропущен пост: Ошибка генерации текста (проверьте OpenAI API).", user_id=user_id)
                return

                # FALLBACK REMOVED as per user request to avoid low-quality posts
                # Enhanced fallback content with available product data
                # ... (fallback code removed) ...

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
        image_urls = content_result.get('product_images') or product_data.get('ImageURLs', []) # Use ImageURLs
        channels = params.get('channels', [])
        successful_posts = 0

        for channel_name in channels:
            # Create channel-specific UTM link
            if base_affiliate_link:
                # Определяем какой track_id использовать (канал или кампания)
                channel_track_id = channel_tracking_ids.get(channel_name)
                campaign_track_id = campaign.get('track_id')
                
                # Приоритет: channel track_id > campaign track_id
                target_tag = channel_track_id or campaign_track_id
                
                # Заменяем tag в ссылке (если есть новый tag)
                if target_tag:
                    working_link = replace_affiliate_tag(base_affiliate_link, target_tag)
                    print(f"✅ Replaced affiliate tag with: {target_tag} for {channel_name}")
                else:
                    working_link = base_affiliate_link
                
                # Добавляем UTM параметры
                utm_params = []
                for param, value in utm_marks.items():
                    utm_params.append(f"{param}={value}")

                # Add campaign-specific UTM if not present
                if 'utm_campaign' not in utm_marks:
                    utm_params.append(f"utm_campaign={campaign['name'].replace(' ', '_')}")

                if utm_params:
                    utm_string = "&".join(utm_params)
                    final_link = f"{working_link}{'&' if '?' in working_link else '?'}{utm_string}"
                else:
                    final_link = working_link
            else:
                final_link = base_affiliate_link

            # Create channel-specific text content
            text_content = base_text_content
            if final_link:
                link_text = sheets_api.get_link_format()
                text_content += f"\n\n[{link_text}]({final_link})"

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
                    image_stream = self._download_image(image_urls[0])
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
                        image_stream = self._download_image(url)
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
        print(f"📦 Posting queued product: {product_data.get('asin', 'Unknown')} - {product_data.get('Title', 'Unknown')[:50]}...")

        # Quality check: ensure product has essential data (price + title) before posting
        has_price = product_data.get('price') is not None and product_data.get('price') > 0
        has_title = product_data.get('Title') and product_data.get('Title').strip()

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
        
        # Get category from campaign for template selection
        campaign_categories = params.get('categories', [])
        category = None
        if campaign_categories and isinstance(campaign_categories, list) and len(campaign_categories) > 0:
            category = campaign_categories[0]

        # Use enriched product data directly - content generator now handles multiple formats
        formatted_product_data = {
            'asin': product_data.get('asin', ''),
            'title': product_data.get('Title', ''),
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
            content_result = await content_generator.generate_post_content(formatted_product_data, language=language, category=category)

            # Convert to post content format if needed
            if content_result and not isinstance(content_result, dict):
                content_result = {
                    'text': content_result.get('content', ''),
                    'hashtags': content_result.get('hashtags', '#Product #Affiliate'),
                    'product_link': formatted_product_data.get('affiliate_link', ''),
                    'product_images': formatted_product_data.get('image_urls', [])
                }

            if not content_result:
                error_msg = f"Генерация контента не удалась (LLM Error), пропускаем пост для очереди кампании {campaign['name']}"
                print(f"⚠️  {error_msg}")
                await self._notify_user(f"🚨 Пропущен пост из очереди: Ошибка генерации текста.", user_id=user_id)
                return

                # FALLBACK REMOVED for queued products too
                # ... (fallback code removed) ...

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
        image_urls = content_result.get('product_images') or formatted_product_data.get('image_urls', []) # use image_urls
        channels = params.get('channels', [])
        successful_posts = 0

        # Store channel-specific links for statistics logging
        channel_links = {}

        for channel_name in channels:
            # Create channel-specific UTM link
            if base_affiliate_link:
                # Определяем какой track_id использовать (канал или кампания)
                channel_track_id = channel_tracking_ids.get(channel_name)
                campaign_track_id = campaign.get('track_id')
                
                # Приоритет: channel track_id > campaign track_id
                target_tag = channel_track_id or campaign_track_id
                
                # Заменяем tag в ссылке (если есть новый tag)
                if target_tag:
                    working_link = replace_affiliate_tag(base_affiliate_link, target_tag)
                    print(f"✅ Replaced affiliate tag with: {target_tag} for {channel_name}")
                else:
                    working_link = base_affiliate_link
                
                # Добавляем UTM параметры
                utm_params = []
                for param, value in utm_marks.items():
                    utm_params.append(f"{param}={value}")

                # Add campaign-specific UTM if not present
                if 'utm_campaign' not in utm_marks:
                    utm_params.append(f"utm_campaign={campaign['name'].replace(' ', '_')}")

                if utm_params:
                    utm_string = "&".join(utm_params)
                    final_link = f"{working_link}{'&' if '?' in working_link else '?'}{utm_string}"
                else:
                    final_link = working_link
            else:
                final_link = base_affiliate_link

            # Store channel-specific link for stats logging
            channel_links[channel_name] = final_link

            # Create channel-specific text content
            text_content = base_text_content
            if final_link:
                link_text = sheets_api.get_link_format()
                text_content += f"\n\n[{link_text}]({final_link})"

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
                    image_stream = self._download_image(image_urls[0])
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
                        image_stream = self._download_image(url)
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
