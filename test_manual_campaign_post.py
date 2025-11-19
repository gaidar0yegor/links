#!/usr/bin/env python3
"""
Manual test script to trigger a post from a specific campaign
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.campaign_manager import CampaignManager, get_campaign_manager, set_campaign_manager
from services.post_manager import PostManager
from db.postgres import init_db_pool
from aiogram import Bot
from config import conf

async def test_campaign_post():
    """Test posting from a specific campaign"""

    # Initialize database
    db_pool = await init_db_pool()
    if not db_pool:
        print('❌ Database connection failed')
        return

    # Initialize campaign manager
    campaign_manager = CampaignManager(db_pool=db_pool)
    set_campaign_manager(campaign_manager)

    # Get active campaigns
    active_campaigns = await campaign_manager.get_active_campaigns_with_timings()
    print(f'📊 Found {len(active_campaigns)} active campaigns')

    # Find a test campaign with sales rank filtering
    test_campaign = None
    for campaign in active_campaigns:
        if campaign['name'].startswith('test_') and campaign['params'].get('max_sales_rank'):
            test_campaign = campaign
            break

    if not test_campaign:
        print('❌ No test campaign with sales rank filtering found')
        return

    print(f'🎯 Testing campaign: {test_campaign["name"]}')
    print(f'📊 Sales rank threshold: {test_campaign["params"].get("max_sales_rank")}')
    print(f'📢 Channels: {test_campaign["params"].get("channels")}')

    # Initialize bot and post manager
    bot_token = conf.bot_token
    if not bot_token:
        print('❌ BOT_TOKEN not found in config')
        return

    bot = Bot(token=bot_token)
    post_manager = PostManager(bot=bot)

    try:
        print('🚀 Starting post process...')
        await post_manager.fetch_and_post_enhanced(test_campaign)
        print('✅ Post process completed successfully')
    except Exception as e:
        print(f'❌ Error during posting: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_campaign_post())
