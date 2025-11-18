#!/usr/bin/env python3
"""
Test script for Amazon web scraper
"""

import asyncio
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.amazon_scraper import AmazonProductScraper

async def test_scraper():
    """Test the Amazon product scraper with a real ASIN."""
    print("🧪 Testing Amazon Product Scraper...")

    # Test with a real product ASIN from the logs (this should be a physical product)
    test_asin = "B086P7H15F"  # PUMA Sports Bag from the logs

    async with AmazonProductScraper() as scraper:
        print(f"🔍 Scraping product data for ASIN: {test_asin}")
        data = await scraper.scrape_product_data(test_asin)

        if data:
            print("✅ Scraping successful!")
            print(f"📦 Title: {data.get('title')}")
            print(f"💰 Price: {data.get('price')} {data.get('currency')}")
            print(f"⭐ Rating: {data.get('rating')}")
            print(f"📝 Reviews: {data.get('review_count')}")
            print(f"🏆 Sales Rank: {data.get('sales_rank')}")
            print(f"📋 Features: {data.get('features')[:2] if data.get('features') else 'None'}")
        else:
            print("❌ Scraping failed - no data returned")

if __name__ == "__main__":
    asyncio.run(test_scraper())
