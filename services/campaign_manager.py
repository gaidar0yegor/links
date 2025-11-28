# services/campaign_manager.py
from typing import List, Dict, Any
from datetime import datetime, time
from db.postgres import db_pool # Используем глобальный пул
import asyncpg

class CampaignManager:
    """Управление операциями с рекламными кампаниями в PostgreSQL."""
    def __init__(self, db_pool: asyncpg.pool.Pool):
        self.db_pool = db_pool

    async def get_all_campaigns_summary(self) -> List[Dict[str, Any]]:
        """
        Получает список кампаний, их статус и наличие таймингов
        (Требование 2.3.1 - Редактировать существующую)
        """
        query = """
        SELECT
            c.id,
            c.name,
            c.status,
            EXISTS (SELECT 1 FROM campaign_timings ct WHERE ct.campaign_id = c.id) AS has_timing
        FROM
            campaigns c
        ORDER BY
            c.name;
        """
        async with self.db_pool.acquire() as conn:
            # Используем fetch, чтобы получить список записей
            records = await conn.fetch(query)

            summary = []
            for r in records:
                # Определение статуса согласно ТЗ
                if r['status'] == 'stopped':
                    status_text = "Не запущена"
                elif r['status'] == 'running':
                    status_text = "Запущена"
                elif r['has_timing'] is False:
                    # Если статус не running/stopped, и нет тайминга
                    status_text = "Не выбраны тайминги"
                else:
                    status_text = r['status'] # Используем статус из БД как запасной

                summary.append({
                    'id': r['id'],
                    'name': r['name'],
                    'status': status_text,
                    'db_status': r['status'] # Фактический статус в БД
                })
            return summary

    async def is_name_unique(self, name: str) -> bool:
        """Проверяет, существует ли кампания с таким названием."""
        query = "SELECT EXISTS(SELECT 1 FROM campaigns WHERE name = $1);"
        async with self.db_pool.acquire() as conn:
            # fetchval вернет одно значение из запроса (True или False)
            exists = await conn.fetchval(query, name)
            return not exists # Возвращаем True, если НЕ существует (т.е. уникально)

    async def save_new_campaign(self, campaign_data: dict) -> int:
        """Сохраняет новую кампанию в БД и возвращает ее ID."""
        # Extract values for separate columns
        name = campaign_data.pop('name')
        created_by_user_id = campaign_data.pop('created_by_user_id', None)
        status = 'timingless'  # Initial status - timings not set yet

        # Extract additional parameters for separate columns
        min_review_count = campaign_data.pop('min_review_count', 0)
        posting_frequency = campaign_data.pop('posting_frequency', 0)
        track_id = campaign_data.pop('track_id', None)

        # Clean data for JSONB params (remove keys that are stored separately)
        params_json = {
            'channels': campaign_data.get('channels', []),
            'categories': campaign_data.get('categories', []),
            'subcategories': campaign_data.get('subcategories', {}),
            'min_rating': campaign_data.get('rating'),
            'language': campaign_data.get('language'),
            'browse_node_ids': campaign_data.get('browse_node_ids', []),
            # Keep legacy filters for backward compatibility
            'min_price': campaign_data.get('min_price'),
            'min_saving_percent': campaign_data.get('min_saving_percent'),
            'fulfilled_by_amazon': campaign_data.get('fulfilled_by_amazon'),
            'max_sales_rank': campaign_data.get('max_sales_rank', 10000),
        }

        import json
        # Updated query with new columns
        query = """
        INSERT INTO campaigns (
            name, status, params, created_by_user_id,
            min_review_count, posting_frequency, track_id
        ) VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7)
        RETURNING id;
        """
        async with self.db_pool.acquire() as conn:
            campaign_id = await conn.fetchval(
                query, name, status, json.dumps(params_json),
                created_by_user_id, min_review_count, posting_frequency, track_id
            )
            return campaign_id

    async def get_campaign_details(self, campaign_id: int) -> Dict[str, Any] | None:
        """Получает полные детали кампании по ID."""
        query = "SELECT id, name, status, params FROM campaigns WHERE id = $1;"
        async with self.db_pool.acquire() as conn:
            record = await conn.fetchrow(query, campaign_id)
            if record:
                # Преобразуем record в словарь
                campaign_dict = dict(record)
                # Парсим JSON params если это строка
                if isinstance(campaign_dict.get('params'), str):
                    import json
                    try:
                        campaign_dict['params'] = json.loads(campaign_dict['params'])
                    except json.JSONDecodeError:
                        # Если не удается распарсить, оставляем как есть
                        pass
                return campaign_dict
            return None

    async def get_campaign_details_full(self, campaign_id: int) -> Dict[str, Any] | None:
        """Получает полные детали кампании по ID, включая все поля."""
        query = """
        SELECT id, name, status, params, created_by_user_id, min_review_count,
               posting_frequency, track_id
        FROM campaigns WHERE id = $1;
        """
        async with self.db_pool.acquire() as conn:
            record = await conn.fetchrow(query, campaign_id)
            if record:
                # Преобразуем record в словарь
                campaign_dict = dict(record)
                # Парсим JSON params если это строка
                if isinstance(campaign_dict.get('params'), str):
                    import json
                    try:
                        campaign_dict['params'] = json.loads(campaign_dict['params'])
                    except json.JSONDecodeError:
                        # Если не удается распарсить, оставляем как есть
                        pass
                return campaign_dict
            return None

    async def update_status(self, campaign_id: int, new_status: str):
        """Обновляет статус кампании (запущена/остановлена)."""
        query = "UPDATE campaigns SET status = $1 WHERE id = $2;"
        async with self.db_pool.acquire() as conn:
            await conn.execute(query, new_status, campaign_id)

    async def has_timings(self, campaign_id: int) -> bool:
        """Проверяет наличие таймингов для кампании."""
        query = "SELECT EXISTS(SELECT 1 FROM campaign_timings WHERE campaign_id = $1);"
        async with self.db_pool.acquire() as conn:
            exists = await conn.fetchval(query, campaign_id)
            return exists

    async def save_timing(self, campaign_id: int, day: int, start_time: str, end_time: str):
        """Сохраняет тайминг для кампании (день/время начала/конца)."""
        query = """
        INSERT INTO campaign_timings (campaign_id, day_of_week, start_time, end_time)
        VALUES ($1, $2, $3::time, $4::time)
        ON CONFLICT (campaign_id, day_of_week, start_time)
        DO UPDATE SET end_time = EXCLUDED.end_time;
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(query, campaign_id, day, start_time, end_time)

    async def get_timings(self, campaign_id: int) -> List[Dict]:
        """Получает все тайминги для кампании."""
        query = "SELECT day_of_week, start_time, end_time FROM campaign_timings WHERE campaign_id = $1 ORDER BY day_of_week, start_time;"
        async with self.db_pool.acquire() as conn:
            records = await conn.fetch(query, campaign_id)
            return [dict(r) for r in records]

    async def get_active_campaigns_with_timings(self) -> List[Dict[str, Any]]:
        """Получает активные кампании (status='running') вместе с их таймингами."""

        # 1. Запрос активных кампаний (сортировка по ID для консистентности)
        # ДОБАВЛЕНО: posting_frequency, last_post_time для корректной работы шедулера
        campaigns_query = "SELECT id, name, params, min_review_count, posting_frequency, last_post_time FROM campaigns WHERE status = 'running' ORDER BY id;"
        async with self.db_pool.acquire() as conn:
            campaign_records = await conn.fetch(campaigns_query)

            if not campaign_records:
                return []

            campaigns = [dict(r) for r in campaign_records]

            # Parse params from JSON string to dict
            import json
            for campaign in campaigns:
                if isinstance(campaign.get('params'), str):
                    try:
                        campaign['params'] = json.loads(campaign['params'])
                    except json.JSONDecodeError:
                        campaign['params'] = {}
                
                # Add min_review_count to params so post_manager can use it
                if 'min_review_count' in campaign:
                    campaign['params']['min_review_count'] = campaign['min_review_count']

            campaign_ids = [c['id'] for c in campaigns]

            # 2. Запрос всех таймингов для этих кампаний
            # Используем $1 для передачи списка ID
            timings_query = """
            SELECT campaign_id, day_of_week, start_time, end_time
            FROM campaign_timings
            WHERE campaign_id = ANY($1::int[])
            ORDER BY campaign_id, day_of_week;
            """
            timing_records = await conn.fetch(timings_query, campaign_ids)

        # 3. Объединение данных
        timing_map = {}
        for t in timing_records:
            cid = t['campaign_id']
            if cid not in timing_map:
                timing_map[cid] = []
            timing_map[cid].append({
                'day_of_week': t['day_of_week'],
                'start_time': t['start_time'],
                'end_time': t['end_time']
            })

        # 4. Добавление таймингов к кампаниям
        for campaign in campaigns:
            campaign['timings'] = timing_map.get(campaign['id'], [])

        return campaigns

    async def get_conflicting_campaigns(self, campaign_id: int, day_of_week: int, current_time: Any) -> List[str]:
        """
        Проверяет, есть ли другая запущенная кампания (status='running', id != campaign_id),
        которая имеет активный тайминг в текущее время И имеет общий канал.
        Возвращает список общих каналов, в которых происходит конфликт.
        """

        # 1. Получаем каналы текущей кампании
        current_campaign_details = await self.get_campaign_details(campaign_id)
        current_channels = current_campaign_details['params'].get('channels', [])
        if not current_channels: return []

        # 2. Convert time to time object for database query
        if isinstance(current_time, str):
            current_time_obj = datetime.strptime(current_time, "%H:%M").time()
        elif isinstance(current_time, time):
            current_time_obj = current_time
        else:
            raise ValueError(f"current_time must be str or time, got {type(current_time)}")

        # 3. Запрос ID запущенных кампаний, активных сейчас (по таймингу)
        active_timing_ids_query = """
        SELECT campaign_id FROM campaign_timings
        WHERE day_of_week = $1
        AND $2 >= start_time
        AND $2 < end_time;
        """

        # 4. Запрос всех запущенных кампаний (кроме текущей)
        running_campaigns_query = "SELECT id, name, params FROM campaigns WHERE status = 'running' AND id != $1;"

        async with self.db_pool.acquire() as conn:
            # Получаем ID кампаний, которые активны по времени
            active_timing_records = await conn.fetch(active_timing_ids_query, day_of_week, current_time_obj)
            active_timing_ids = {r['campaign_id'] for r in active_timing_records}

            conflicting_channels = set()

            running_campaigns_records = await conn.fetch(running_campaigns_query, campaign_id)
            
            # Parse params from JSON string to dict
            import json
            running_campaigns = []
            for r in running_campaigns_records:
                campaign = dict(r)
                if isinstance(campaign.get('params'), str):
                    try:
                        campaign['params'] = json.loads(campaign['params'])
                    except json.JSONDecodeError:
                        campaign['params'] = {}
                running_campaigns.append(campaign)


            for rc in running_campaigns:
                # Parse params from JSON string to dict if needed
                rc_params = rc['params']
                if isinstance(rc_params, str):
                    import json
                    try:
                        rc_params = json.loads(rc_params)
                    except json.JSONDecodeError:
                        rc_params = {}

                # Проверяем, активна ли эта кампания в текущее время
                if rc['id'] in active_timing_ids:
                    # Проверяем пересечение каналов
                    rc_channels = rc_params.get('channels', [])

                    for channel in current_channels:
                        if channel in rc_channels:
                            conflicting_channels.add(channel)

            return list(conflicting_channels)

    async def mark_last_post_time(self, campaign_id: int, post_time: datetime):
        """Обновляет время последнего поста (для предотвращения повторного постинга в интервале)."""
        query = "UPDATE campaigns SET last_post_time = $1 WHERE id = $2;"
        async with self.db_pool.acquire() as conn:
            await conn.execute(query, post_time, campaign_id)

    async def log_post_statistics(self, data: dict):
        """Логирует статистику поста в таблицу statistics_log (ТЗ 3.2)."""
        query = """
        INSERT INTO statistics_log (campaign_id, channel_name, asin, final_link)
        VALUES ($1, $2, $3, $4);
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                query,
                data['campaign_id'],
                data['channel_name'],
                data.get('asin'),
                data['final_link']
            )

    async def get_posted_asins(self, campaign_id: int, limit: int = 1000) -> List[str]:
        """
        Get list of ASINs already posted or queued by this campaign to prevent duplicates.
        Returns the most recent posted/queued ASINs (up to limit).
        """
        query = """
        SELECT asin
        FROM (
            SELECT asin FROM statistics_log
            WHERE campaign_id = $1 AND asin IS NOT NULL AND asin != ''
            UNION
            SELECT asin FROM product_queue
            WHERE campaign_id = $1 AND asin IS NOT NULL AND asin != ''
        ) AS all_asins
        GROUP BY asin
        ORDER BY MAX(
            COALESCE(
                (SELECT MAX(post_time) FROM statistics_log WHERE campaign_id = $1 AND asin = all_asins.asin),
                (SELECT MAX(discovered_at) FROM product_queue WHERE campaign_id = $1 AND asin = all_asins.asin),
                '1970-01-01'::timestamp
            )
        ) DESC
        LIMIT $2;
        """
        async with self.db_pool.acquire() as conn:
            records = await conn.fetch(query, campaign_id, limit)
            return [record['asin'] for record in records]

    async def delete_campaign(self, campaign_id: int):
        """Удаляет кампанию и все связанные с ней тайминги (CASCADE DELETE)."""
        query = "DELETE FROM campaigns WHERE id = $1;"
        async with self.db_pool.acquire() as conn:
            await conn.execute(query, campaign_id)

    async def get_enhanced_campaign_config(self, campaign_id: int) -> Dict[str, Any]:
        """
        Get enhanced campaign configuration with Google Sheets integration.
        Includes content templates, posting schedules, and product filters.
        """
        campaign = await self.get_campaign_details(campaign_id)
        if not campaign:
            return None

        # Import services for enhanced functionality
        try:
            from services.content_generator import content_generator
            from services.posting_scheduler import posting_scheduler
            from services.product_filter import product_filter
            from services.sheets_api import sheets_api
        except ImportError:
            # Services not available, return basic config
            return campaign

        # Get campaign parameters
        params = campaign.get('params', {})

        # Enhance with Google Sheets data
        enhanced_config = dict(campaign)
        enhanced_config['enhanced_features'] = {
            'content_templates': self._get_available_templates(params.get('categories', [])),
            'posting_schedules': posting_scheduler.get_all_schedules(),
            'product_filters': product_filter.get_all_filters(),
            'utm_parameters': sheets_api.get_utm_marks(),
            'available_channels': self._get_available_channels()
        }

        return enhanced_config

    def _get_available_templates(self, categories: List[str]) -> Dict[str, List[Dict]]:
        """Get available content templates for given categories."""
        try:
            from services.content_generator import content_generator
            templates = {}

            for category in categories:
                # Get templates for this category
                template = content_generator.get_random_template(category)
                if template:
                    if category not in templates:
                        templates[category] = []
                    templates[category].append(template)

            return templates
        except ImportError:
            return {}

    def _get_available_channels(self) -> List[Dict[str, str]]:
        """Get available posting channels from Google Sheets."""
        try:
            from services.sheets_api import sheets_api
            channels_data = sheets_api.get_sheet_data('channels')

            if not channels_data or len(channels_data) < 2:
                return []

            channels = []
            for row in channels_data[1:]:  # Skip header
                if len(row) >= 2:
                    channels.append({
                        'name': row[0],
                        'id': row[1]
                    })

            return channels
        except Exception:
            return []

    async def create_enhanced_campaign(self, campaign_data: Dict[str, Any]) -> int:
        """
        Create a campaign with enhanced Google Sheets integration.
        Supports content templates, posting schedules, and product filters.
        """
        # Extract enhanced parameters
        content_template = campaign_data.pop('content_template', None)
        posting_schedule = campaign_data.pop('posting_schedule', None)
        product_filter = campaign_data.pop('product_filter', None)

        # Create basic campaign first
        campaign_id = await self.save_new_campaign(campaign_data)

        # Add enhanced configuration if provided
        if campaign_id:
            enhanced_params = {}

            if content_template:
                enhanced_params['content_template_id'] = content_template
            if posting_schedule:
                enhanced_params['posting_schedule_id'] = posting_schedule
            if product_filter:
                enhanced_params['product_filter_id'] = product_filter

            if enhanced_params:
                # Update campaign with enhanced parameters
                await self._update_enhanced_params(campaign_id, enhanced_params)

        return campaign_id

    async def _update_enhanced_params(self, campaign_id: int, enhanced_params: Dict[str, Any]):
        """Update campaign with enhanced parameters."""
        import json

        query = """
        UPDATE campaigns
        SET params = params || $1::jsonb
        WHERE id = $2;
        """

        async with self.db_pool.acquire() as conn:
            await conn.execute(query, json.dumps(enhanced_params), campaign_id)

    async def get_campaign_performance(self, campaign_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get campaign performance analytics.
        Includes posting statistics, engagement metrics, and conversion data.
        """
        # Get basic campaign info
        campaign = await self.get_campaign_details(campaign_id)
        if not campaign:
            return None

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - datetime.timedelta(days=days)

        # Query performance data
        query = """
        SELECT
            COUNT(*) as total_posts,
            COUNT(DISTINCT DATE(created_at)) as active_days,
            AVG(CASE WHEN engagement_rate > 0 THEN engagement_rate END) as avg_engagement,
            SUM(clicks) as total_clicks,
            SUM(orders) as total_orders,
            SUM(revenue) as total_revenue
        FROM campaign_analytics
        WHERE campaign_id = $1 AND created_at >= $2 AND created_at <= $3;
        """

        async with self.db_pool.acquire() as conn:
            analytics = await conn.fetchrow(query, campaign_id, start_date, end_date)

        # Get recent posts performance
        recent_posts_query = """
        SELECT created_at, clicks, orders, revenue, engagement_rate
        FROM campaign_analytics
        WHERE campaign_id = $1 AND created_at >= $2
        ORDER BY created_at DESC
        LIMIT 10;
        """

        recent_posts = await conn.fetch(recent_posts_query, campaign_id, start_date)

        return {
            'campaign_info': campaign,
            'period_days': days,
            'total_posts': analytics['total_posts'] or 0,
            'active_days': analytics['active_days'] or 0,
            'avg_engagement': float(analytics['avg_engagement'] or 0),
            'total_clicks': analytics['total_clicks'] or 0,
            'total_orders': analytics['total_orders'] or 0,
            'total_revenue': float(analytics['total_revenue'] or 0),
            'recent_posts': [dict(post) for post in recent_posts]
        }

    async def get_campaign_recommendations(self, campaign_id: int) -> List[str]:
        """
        Generate AI-powered recommendations for campaign optimization.
        """
        performance = await self.get_campaign_performance(campaign_id, days=7)

        if not performance or performance['total_posts'] == 0:
            return ["Start posting to gather performance data for recommendations."]

        recommendations = []

        # Analyze posting frequency
        avg_posts_per_day = performance['total_posts'] / max(performance['active_days'], 1)
        if avg_posts_per_day < 1:
            recommendations.append("Consider increasing posting frequency to improve visibility.")
        elif avg_posts_per_day > 3:
            recommendations.append("High posting frequency detected. Monitor for engagement fatigue.")

        # Analyze engagement
        if performance['avg_engagement'] < 0.02:  # Less than 2%
            recommendations.append("Low engagement detected. Try different content templates or posting times.")
        elif performance['avg_engagement'] > 0.05:  # More than 5%
            recommendations.append("Excellent engagement! Current strategy is working well.")

        # Analyze conversion
        if performance['total_orders'] > 0:
            conversion_rate = performance['total_orders'] / performance['total_clicks'] if performance['total_clicks'] > 0 else 0
            if conversion_rate < 0.01:  # Less than 1%
                recommendations.append("Low conversion rate. Consider reviewing product selection or affiliate links.")
        else:
            recommendations.append("No orders recorded yet. Focus on driving traffic to affiliate links.")

        # Time-based recommendations
        campaign = await self.get_campaign_details(campaign_id)
        timings = await self.get_timings(campaign_id)

        if not timings:
            recommendations.append("No posting schedule configured. Set up optimal posting times.")
        elif len(timings) < 3:
            recommendations.append("Limited posting schedule. Consider expanding to more time slots.")

        return recommendations if recommendations else ["Campaign is performing well. Continue current strategy."]

    # ===== PRODUCT QUEUE MANAGEMENT =====

    async def add_product_to_queue(self, campaign_id: int, product_data: Dict[str, Any]) -> int:
        """
        Add a vetted product to the product queue.
        """
        query = """
        INSERT INTO product_queue (
            campaign_id, asin, title, price, currency, rating, review_count,
            sales_rank, image_urls, affiliate_link, browse_node_ids, quality_score, features
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id;
        """

        async with self.db_pool.acquire() as conn:
            product_id = await conn.fetchval(
                query,
                campaign_id,
                product_data['asin'],
                product_data.get('title'),
                product_data.get('price'),
                product_data.get('currency'),
                product_data.get('rating'),
                product_data.get('review_count'),
                product_data.get('sales_rank'),
                product_data.get('image_urls', []), # Changed from image_url
                product_data.get('affiliate_link'),
                product_data.get('browse_node_ids', []),
                product_data.get('sales_rank'),  # Quality score = sales rank
                product_data.get('features', [])
            )
            return product_id

    async def get_next_queued_product(self, campaign_id: int) -> Dict[str, Any] | None:
        """
        Get the next product from the queue for a specific campaign.
        Returns the oldest queued product.
        """
        query = """
        SELECT * FROM product_queue
        WHERE campaign_id = $1 AND status = 'queued'
        ORDER BY discovered_at ASC
        LIMIT 1;
        """

        async with self.db_pool.acquire() as conn:
            record = await conn.fetchrow(query, campaign_id)
            if record:
                # Convert to dict and parse browse_node_ids
                product = dict(record)
                # browse_node_ids is already an array in PostgreSQL
                return product
            return None

    async def mark_product_posted(self, product_id: int):
        """
        Mark a product as posted and update the timestamp.
        """
        query = """
        UPDATE product_queue
        SET status = 'posted', posted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = $1;
        """

        async with self.db_pool.acquire() as conn:
            await conn.execute(query, product_id)

    async def get_queue_size(self, campaign_id: int) -> int:
        """
        Get the number of queued products for a campaign.
        """
        query = "SELECT COUNT(*) FROM product_queue WHERE campaign_id = $1 AND status = 'queued';"

        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(query, campaign_id)
            return count or 0

    async def populate_queue_for_campaign(self, campaign_id: int, limit: int = 200):
        """
        Immediately populate the product queue for a newly created campaign.
        This addresses the issue where campaigns previously waited 6 hours.
        """
        try:
            # Get campaign details
            campaign = await self.get_campaign_details_full(campaign_id)
            if not campaign:
                print(f"❌ Campaign {campaign_id} not found for queue population")
                return 0

            # Check current queue size to avoid overpopulation
            current_queue_size = await self.get_queue_size(campaign_id)
            if current_queue_size >= limit:
                print(f"✅ Campaign {campaign_id} already has {current_queue_size} products in queue")
                return current_queue_size

            print(f"🔄 Populating queue for campaign {campaign['name']} (ID: {campaign_id})")

            # Import required services (local imports to avoid circular dependencies)
            try:
                from services.amazon_paapi_client import amazon_paapi_client
            except ImportError:
                print(f"⚠️  Amazon PA API client not available, skipping queue population")
                return 0

            params = campaign.get('params', {})
            browse_node_ids = params.get('browse_node_ids', [])

            if not browse_node_ids:
                print(f"⚠️  No browse_node_ids for campaign {campaign_id}, skipping queue population")
                return 0

            # Search for products
            search_results = await amazon_paapi_client.search_items_enhanced(
                browse_node_ids=browse_node_ids,
                min_rating=params.get('min_rating', 4.0),
                min_price=params.get('min_price'),
                fulfilled_by_amazon=params.get('fulfilled_by_amazon'),
                max_sales_rank=params.get('max_sales_rank', 10000),
                min_review_count=campaign.get('min_review_count', 0),
                max_results=min(limit * 2, 50)  # Get more results to filter from
            )

            if not search_results:
                print(f"❌ No products found for campaign {campaign_id}")
                return 0

            # Get already posted ASINs to avoid duplicates
            min_review_count = campaign.get('min_review_count', 0)
            posted_asins = await self.get_posted_asins(campaign_id, limit=5000)

            queued_count = 0
            for product in search_results:
                # Stop if we've reached the desired queue size
                if await self.get_queue_size(campaign_id) >= limit:
                    break

                asin = product.get('asin')
                if not asin or asin in posted_asins:
                    continue

                # Apply review count filter (new feature)
                review_count = product.get('review_count', 0)
                if min_review_count > 0 and review_count < min_review_count:
                    continue

                # Prepare product data
                product_data = {
                    'asin': asin,
                    'title': product.get('title', ''),
                    'price': product.get('price'),
                    'currency': product.get('currency', 'EUR'),
                    'rating': product.get('rating'),
                    'review_count': review_count,
                    'sales_rank': product.get('sales_rank'),
                    'image_urls': product.get('image_urls', []), # Changed from image_url
                    'affiliate_link': product.get('affiliate_link'),
                    'browse_node_ids': browse_node_ids
                }

                try:
                    await self.add_product_to_queue(campaign_id, product_data)
                    queued_count += 1
                    print(f"✅ Added {asin} to queue (rank: {product.get('sales_rank')}, reviews: {review_count})")
                except Exception as e:
                    print(f"❌ Failed to add {asin} to queue: {e}")

            print(f"🎉 Populated queue for campaign {campaign_id} with {queued_count} products")
            return queued_count

        except Exception as e:
            print(f"❌ Failed to populate queue for campaign {campaign_id}: {e}")
            return 0

    async def cleanup_old_products(self, days: int = 30):
        """
        Remove products that have been in the queue for too long without being posted.
        """
        query = """
        DELETE FROM product_queue
        WHERE status = 'queued' AND discovered_at < CURRENT_TIMESTAMP - INTERVAL '%s days';
        """ % days

        async with self.db_pool.acquire() as conn:
            deleted_count = await conn.fetchval("SELECT COUNT(*) FROM product_queue WHERE status = 'queued' AND discovered_at < CURRENT_TIMESTAMP - INTERVAL '%s days';" % days)
            await conn.execute(query)
            return deleted_count or 0

# Глобальная переменная для CampaignManager будет инициализирована в main.py
campaign_manager: CampaignManager | None = None

def set_campaign_manager(manager: CampaignManager):
    """Set the global campaign_manager instance."""
    global campaign_manager
    campaign_manager = manager

def get_campaign_manager():
    """Get the current campaign_manager instance."""
    return campaign_manager
