#!/usr/bin/env python3
"""
Script to initialize Google Sheets with required worksheets and data.
This script creates all necessary worksheets for the Telegram Affiliate Bot.
"""

import gspread
from google.oauth2.service_account import Credentials
from config import conf

def init_google_sheets():
    """Initialize Google Sheets with required worksheets and data."""

    print("🔧 Initializing Google Sheets...")

    try:
        # Setup credentials
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(conf.gsheets.service_account_file, scopes=scopes)
        gc = gspread.authorize(creds)

        # Open the spreadsheet
        spreadsheet = gc.open_by_key(conf.gsheets.spreadsheet_id)
        print(f"✅ Connected to spreadsheet: {spreadsheet.title}")

        # Create worksheets
        worksheets_to_create = [
            {
                'name': 'users_whitelist',
                'headers': ['telegram_id', 'username', 'added_date'],
                'initial_data': [
                    [1451953302, '@users_slayer', '2024-01-01'],
                    [117422597, '@test_user', '2024-01-01'],
                    [954096177, '@admin', '2024-01-01']
                ]
            },
            {
                'name': 'rewrite_prompt',
                'headers': ['Prompt'],
                'initial_data': [
                    ['Rewrite the following text to make it engaging and persuasive and fit for a social media post.']
                ]
            },
            {
                'name': 'utm_marks',
                'headers': ['parameter', 'value'],
                'initial_data': [
                    ['utm_source', 'social_media'],
                    ['utm_medium', 'telegram_bot'],
                    ['utm_campaign', 'affiliate']
                ]
            },
            {
                'name': 'statistics',
                'headers': ['Date', 'Revenue', 'Clicks', 'Sales'],
                'initial_data': [
                    ['2024-01-01', '1000', '500', '50'],
                    ['2024-01-02', '1200', '600', '60']
                ]
            },
            {
                'name': 'channels',
                'headers': ['channel_name', 'channel_id'],
                'initial_data': [
                    ['Telegram Channel 1', 'telegram_1'],
                    ['Telegram Channel 2', 'telegram_2'],
                    ['VK Group', 'vk_group'],
                    ['Instagram', 'instagram']
                ]
            },
            {
                'name': 'categories',
                'headers': ['category_name', 'category_id'],
                'initial_data': [
                    ['Electronics', 'electronics'],
                    ['Books', 'books'],
                    ['Clothing', 'clothing'],
                    ['Home & Garden', 'home_garden']
                ]
            },
            {
                'name': 'subcategories',
                'headers': ['subcategory_name', 'subcategory_id'],
                'initial_data': [
                    ['Smartphones', 'smartphones'],
                    ['Laptops', 'laptops'],
                    ['Fiction Books', 'fiction'],
                    ['Non-Fiction Books', 'non_fiction'],
                    ['T-Shirts', 'tshirts'],
                    ['Jeans', 'jeans']
                ]
            },
            {
                'name': 'languages',
                'headers': ['language_name', 'language_code'],
                'initial_data': [
                    ['Русский', 'ru'],
                    ['English', 'en'],
                    ['Español', 'es'],
                    ['Deutsch', 'de']
                ]
            },
            {
                'name': 'products',
                'headers': ['id', 'name', 'category', 'subcategory', 'price', 'rating', 'reviews_count', 'image_url', 'affiliate_link', 'description', 'active'],
                'initial_data': [
                    ['PROD001', 'Premium Wireless Headphones', 'Electronics', 'Audio', '89.99', '4.5', '1250', 'https://picsum.photos/400/400?random=1', 'https://www.amazon.it/dp/B08N1M9G9Z?tag=cucinaconamor-21', 'High-quality wireless headphones with noise cancellation', 'TRUE'],
                    ['PROD002', 'Professional Camera Lens', 'Electronics', 'Photography', '299.99', '4.7', '890', 'https://picsum.photos/400/400?random=2', 'https://www.amazon.it/dp/B07ZJZ3Q3Q?tag=cucinaconamor-21', '85mm f/1.4 portrait lens for professional photography', 'TRUE'],
                    ['PROD003', 'Organic Green Tea Set', 'Food', 'Beverages', '24.99', '4.3', '567', 'https://picsum.photos/400/400?random=3', 'https://www.amazon.it/dp/B08KJ3Z9Z9?tag=cucinaconamor-21', 'Premium organic green tea assortment from Japan', 'TRUE'],
                    ['PROD004', 'Ergonomic Office Chair', 'Furniture', 'Office', '199.99', '4.6', '2340', 'https://picsum.photos/400/400?random=4', 'https://www.amazon.it/dp/B08N2M9G9Z?tag=cucinaconamor-21', 'Adjustable ergonomic chair for long work sessions', 'TRUE'],
                    ['PROD005', 'Fitness Resistance Bands', 'Sports', 'Fitness', '19.99', '4.4', '1876', 'https://picsum.photos/400/400?random=5', 'https://www.amazon.it/dp/B08KJ3Z9Z9?tag=cucinaconamor-21', 'Set of 5 resistance bands for home workouts', 'TRUE']
                ]
            },
            {
                'name': 'content_templates',
                'headers': ['template_id', 'name', 'template_text', 'hashtags', 'category', 'language'],
                'initial_data': [
                    ['TEMP001', 'Electronics Product', '🔊 Discover the {product_name} - the perfect choice for tech enthusiasts! ⭐ {rating}/5 stars from {reviews_count} reviews. Get yours now: {affiliate_link} #Tech #Gadgets {hashtags}', '#Electronics #Technology #Innovation', 'Electronics', 'en'],
                    ['TEMP002', 'Fitness Product', '💪 Transform your workout with {product_name}! Rated {rating}/5 by {reviews_count} satisfied customers. Limited time offer: {affiliate_link} #Fitness #Health #Workout {hashtags}', '#Fitness #Health #Sports', 'Sports', 'en'],
                    ['TEMP003', 'Home Product', '🏠 Upgrade your home with {product_name} - {rating}/5 stars! Trusted by {reviews_count} customers. Shop now: {affiliate_link} #Home #Decor #Lifestyle {hashtags}', '#HomeDecor #InteriorDesign #Lifestyle', 'Furniture', 'en'],
                    ['TEMP004', 'Food Product', '🍽️ Delicious and healthy: {product_name}! {rating}/5 stars from {reviews_count} reviews. Perfect for your diet: {affiliate_link} #Food #Healthy #Nutrition {hashtags}', '#Foodie #HealthyEating #Nutrition', 'Food', 'en']
                ]
            },
            {
                'name': 'hashtags',
                'headers': ['category', 'hashtags_list'],
                'initial_data': [
                    ['Electronics', '#Tech #Gadgets #Electronics #Innovation #SmartTech #Gizmo #Device #GadgetLovers'],
                    ['Sports', '#Fitness #Workout #Sports #Health #Training #Exercise #Gym #ActiveLifestyle'],
                    ['Furniture', '#HomeDecor #InteriorDesign #Furniture #Home #Decor #Interior #HomedecorIdeas'],
                    ['Food', '#Foodie #HealthyEating #Nutrition #FoodLovers #HealthyFood #CleanEating #Organic']
                ]
            },
            {
                'name': 'posting_schedules',
                'headers': ['schedule_id', 'name', 'days_of_week', 'time_slots', 'frequency'],
                'initial_data': [
                    ['SCH001', 'Morning Routine', '1,2,3,4,5', '08:00,09:00,10:00', 'daily'],
                    ['SCH002', 'Evening Promotion', '1,2,3,4,5,6,7', '18:00,19:00,20:00', 'daily'],
                    ['SCH003', 'Weekend Special', '6,7', '12:00,15:00,18:00', 'daily'],
                    ['SCH004', 'Business Hours', '1,2,3,4,5', '12:00,13:00,14:00', 'weekdays']
                ]
            },
            {
                'name': 'product_filters',
                'headers': ['filter_id', 'name', 'min_rating', 'min_reviews', 'min_orders', 'price_min', 'price_max', 'profit_min', 'seller_rank_min'],
                'initial_data': [
                    ['FLT001', 'Premium Products', '4.5', '100', '50', '50', '500', '20', '10000'],
                    ['FLT002', 'Budget Friendly', '4.0', '50', '25', '10', '100', '5', '5000'],
                    ['FLT003', 'Top Rated', '4.7', '200', '100', '25', '1000', '15', '20000'],
                    ['FLT004', 'Best Sellers', '4.2', '500', '200', '15', '200', '10', '15000']
                ]
            }
        ]

        for ws_config in worksheets_to_create:
            try:
                # Try to get existing worksheet
                worksheet = spreadsheet.worksheet(ws_config['name'])
                print(f"📋 Worksheet '{ws_config['name']}' already exists, updating...")
            except gspread.exceptions.WorksheetNotFound:
                # Create new worksheet
                worksheet = spreadsheet.add_worksheet(title=ws_config['name'], rows=100, cols=20)
                print(f"📋 Created worksheet '{ws_config['name']}'")

            # Clear existing data
            worksheet.clear()

            # Add headers
            worksheet.update('A1', [ws_config['headers']])

            # Add initial data
            if ws_config['initial_data']:
                for i, row in enumerate(ws_config['initial_data'], start=2):
                    worksheet.update(f'A{i}', [row])

            print(f"✅ Initialized worksheet '{ws_config['name']}' with {len(ws_config['initial_data'])} rows")

        print("\n🎉 Google Sheets initialization completed successfully!")
        print("\n📋 Created worksheets:")
        print("   • users_whitelist - Authorized Telegram user IDs")
        print("   • rewrite_prompt - AI content rewriting prompts")
        print("   • utm_marks - UTM tracking parameters")
        print("   • statistics - Sales statistics data")

    except Exception as e:
        print(f"❌ Error initializing Google Sheets: {e}")
        return False

    return True

if __name__ == "__main__":
    success = init_google_sheets()
    if success:
        print("\n🚀 Your Telegram Affiliate Bot is now ready with real Google Sheets data!")
    else:
        print("\n❌ Failed to initialize Google Sheets. Please check your configuration.")
