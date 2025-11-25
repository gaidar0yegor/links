# test_notifications.py
import asyncio
import sys
from aiogram import Bot
from config import conf
from services.sheets_api import sheets_api

async def test_get_users_for_notification():
    """Test the get_users_for_notification method using actual Google Sheets API."""
    print("🧪 Testing get_users_for_notification with Google Sheets API...")
    
    print("\n📡 Fetching data from Google Sheets...")
    try:
        # Get actual data from Google Sheets
        notify_users = sheets_api.get_users_for_notification()
        
        print(f"\n✅ Successfully retrieved {len(notify_users)} user(s) with notifications enabled")
        if notify_users:
            print(f"   User IDs: {notify_users}")
        else:
            print("   ⚠️ No users found with notifications enabled")
            print("   This could mean:")
            print("   1. The 'notification' column doesn't exist in users_whitelist")
            print("   2. No users have 'Yes', 'TRUE', '1', or '+' in the notification column")
            print("   3. The Google Sheets API is not available (using dummy data)")
        
        # Also test the raw sheet data to see structure
        print("\n📊 Checking raw sheet data structure...")
        sheet_data = sheets_api.get_sheet_data("users_whitelist")
        if sheet_data:
            print(f"   Found {len(sheet_data)} rows in users_whitelist")
            if len(sheet_data) > 0:
                print(f"   Headers: {sheet_data[0]}")
                if len(sheet_data) > 1:
                    print(f"   First data row: {sheet_data[1]}")
        else:
            print("   ⚠️ Could not retrieve sheet data")
        
    except Exception as e:
        print(f"❌ Error testing get_users_for_notification: {e}")
        import traceback
        traceback.print_exc()

async def send_test_notifications():
    """Send actual test messages to users with notifications enabled."""
    print("\n" + "="*60)
    print("📨 Sending test notifications to users...")
    print("="*60)
    
    # Initialize bot
    if not conf.bot_token:
        print("❌ BOT_TOKEN not found in environment variables")
        return
    
    bot = Bot(token=conf.bot_token)
    
    try:
        # Get users with notifications enabled from Google Sheets API
        print("📡 Fetching users from Google Sheets...")
        notify_users = sheets_api.get_users_for_notification()
        
        if not notify_users:
            print("⚠️ No users found with notifications enabled")
            print("   Make sure:")
            print("   1. The 'notification' column exists in users_whitelist sheet")
            print("   2. At least one user has 'Yes', 'TRUE', '1', or '+' in the notification column")
            return
        
        print(f"📋 Found {len(notify_users)} user(s) with notifications enabled: {notify_users}")
        
        test_message = (
            "🧪 <b>Test Notification</b>\n\n"
            "Это тестовое уведомление от бота.\n"
            "Если вы получили это сообщение, значит система уведомлений работает корректно! ✅"
        )
        
        success_count = 0
        failed_count = 0
        
        for user_id in notify_users:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=test_message,
                    parse_mode="HTML"
                )
                print(f"✅ Message sent successfully to user {user_id}")
                success_count += 1
            except Exception as e:
                print(f"❌ Failed to send message to user {user_id}: {e}")
                failed_count += 1
        
        print("\n" + "="*60)
        print(f"📊 Summary: {success_count} successful, {failed_count} failed")
        print("="*60)
        
    finally:
        await bot.session.close()

async def main():
    # Run logic tests first
    await test_get_users_for_notification()
    
    # Ask user if they want to send actual messages
    print("\n" + "="*60)
    response = input("Do you want to send actual test messages? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y', 'да', 'д']:
        await send_test_notifications()
    else:
        print("Skipping actual message sending.")

if __name__ == "__main__":
    asyncio.run(main())
