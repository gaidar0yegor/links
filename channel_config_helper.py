#!/usr/bin/env python3
"""
Channel Configuration Helper for Telegram Affiliate Bot

This script helps you configure your Telegram channel for automated posting.
Run this to generate the proper Google Sheets configuration.
"""

def generate_campaign_config(channel_link="t.me/CheapAmazon3332234"):
    """Generate campaign configuration for Google Sheets."""

    print("🚀 Telegram Affiliate Bot - Channel Configuration Helper")
    print("=" * 60)

    # Use provided channel or default
    if not channel_link or "t.me/" not in channel_link:
        print("❌ Invalid channel link format. Should be like: t.me/YourChannel")
        return

    # Extract channel username
    channel_username = "@" + channel_link.split("t.me/")[1]

    print(f"\n✅ Channel configured: {channel_username}")
    print(f"   Original link: {channel_link}")

    # Default campaign details for CheapAmazon3332234
    campaign_name = "Cheap Amazon Deals"
    categories = "electronics,home,kitchen,garden"
    min_rating = "4.0"

    print("\n📋 GOOGLE SHEETS CONFIGURATION:")
    print("=" * 40)

    print("\nCreate a worksheet named 'campaigns' with these columns:")
    print("Campaign Name | Channels | Categories | Min Rating | Status")
    print("-" * 60)

    print(f"{campaign_name} | {channel_username} | {categories} | {min_rating} | active")

    print("\n📄 JSON CONFIGURATION (for advanced setup):")
    print("=" * 50)

    # Fix categories formatting
    categories_list = '","'.join(categories.split(','))
    json_config = f'''{{
  "name": "{campaign_name}",
  "channels": ["{channel_username}"],
  "categories": ["{categories_list}"],
  "min_rating": {min_rating},
  "content_template_id": "affiliate_deals",
  "product_filter_id": "top_rated",
  "posting_schedule_id": "daily_3pm",
  "status": "active"
}}'''

    print(json_config)

    print("\n🔧 SETUP CHECKLIST:")
    print("=" * 25)
    print("□ Add bot as channel administrator")
    print("□ Grant 'Post Messages' permission")
    print("□ Create 'campaigns' worksheet in Google Sheets")
    print("□ Copy the configuration above")
    print("□ Restart the bot: docker-compose restart")

    print("\n🧪 TESTING:")
    print("=" * 10)
    print("1. Start bot: docker-compose up -d")
    print("2. Check logs: docker-compose logs -f bot")
    print(f"3. Look for: '✅ Posted to {channel_username}'")

    print("\n💡 TROUBLESHOOTING:")
    print("=" * 20)
    print("• If posting fails, check bot admin permissions")
    print("• Try using channel ID instead of username")
    print("• Verify Google Sheets configuration")

    print("\n🎉 CONFIGURATION COMPLETE!")
    print(f"Your bot will now post to: {channel_username}")
    print("Start earning affiliate commissions! 💰")

if __name__ == "__main__":
    generate_campaign_config()
