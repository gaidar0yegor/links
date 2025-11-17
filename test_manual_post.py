#!/usr/bin/env python3
"""
Manual test script to trigger posting for a specific campaign.
"""
import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.post_manager import PostManager
from services.campaign_manager import CampaignManager, set_campaign_manager
from aiogram import Bot
from config import conf
from db.postgres import init_db_pool

async def test_manual_post(campaign_id: int):
    """Manually trigger posting for a specific campaign."""
    print(f"🚀 Starting manual test post for campaign ID: {campaign_id}")

    # Initialize database pool
    db_pool = await init_db_pool()
    if not db_pool:
        print("❌ Database pool initialization failed")
        return

    # Initialize campaign manager
    campaign_manager = CampaignManager(db_pool=db_pool)
    set_campaign_manager(campaign_manager)

    # Initialize bot
    bot = Bot(token=conf.bot_token)

    # Initialize PostManager
    post_manager = PostManager(bot=bot)

    # Get campaign details
    campaign = await campaign_manager.get_campaign_details(campaign_id)
    if not campaign:
        print(f"❌ Campaign {campaign_id} not found")
        return

    print(f"📋 Campaign: {campaign['name']}")
    print(f"📺 Channels: {campaign['params'].get('channels', [])}")
    print(f"📊 Status: {campaign['status']}")

    # Trigger posting
    try:
        print("🔄 Calling fetch_and_post...")
        await post_manager.fetch_and_post(campaign)
        print("✅ Manual post completed successfully!")
    except Exception as e:
        print(f"❌ Error during manual post: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_manual_post.py <campaign_id>")
        sys.exit(1)

    campaign_id = int(sys.argv[1])
    asyncio.run(test_manual_post(campaign_id))
