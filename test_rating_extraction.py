#!/usr/bin/env python3
"""
Test script to debug rating extraction issues from Amazon product pages.
Tests specific ASINs that are failing to extract ratings.
"""

import asyncio
import sys
import aiohttp
from services.amazon_scraper import AmazonProductScraper
from bs4 import BeautifulSoup
import re


# ASINs from logs that failed rating extraction
TEST_ASINS = [
    "B0G328TTT8",
    "B07ZFP96MS",
    "B0FN49DRGJ",
    "B0G2LQB9RV",
    "B0DTN2X5XF",
    "B0DHW3KXVV",
    "B0FTHBPLST",
    "B0FPCS6TS8",
    "B0F1DCPT15",
    "B0CYC6LHP2",
]


async def test_rating_extraction(asin: str):
    """Test rating extraction for a specific ASIN."""
    print("\n" + "="*80)
    print(f"🔍 Testing ASIN: {asin}")
    print("="*80)
    
    async with AmazonProductScraper() as scraper:
        # Scrape the product page
        product_data = await scraper.scrape_product_data(asin)
        
        if not product_data:
            print(f"❌ Failed to scrape product page for {asin}")
            return
        
        print(f"\n📊 Scraped Data:")
        print(f"   Price: {product_data.get('price')}")
        print(f"   Rating: {product_data.get('rating')}")
        print(f"   Review Count: {product_data.get('review_count')}")
        print(f"   Sales Rank: {product_data.get('sales_rank')}")
        
        # Safe title printing
        title = product_data.get('title')
        if title:
            print(f"   Title: {title[:80]}...")
        else:
            print(f"   Title: N/A")
        
        # Now let's manually check the HTML for rating elements
        print(f"\n🔎 Manual HTML Analysis:")
        url = f"https://www.amazon.it/dp/{asin}"
        
        try:
            async with scraper.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    print(f"   ⚠️  HTTP Status: {response.status}")
                    return
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Check for rating elements using current selectors
                print(f"\n   📍 Checking current selectors:")
                
                # Selector 1: #averageCustomerReviews .a-icon-star .a-icon-alt
                rating_elem1 = soup.select_one('#averageCustomerReviews .a-icon-star .a-icon-alt')
                if rating_elem1:
                    rating_text1 = rating_elem1.get_text()
                    print(f"   ✅ Found with selector '#averageCustomerReviews .a-icon-star .a-icon-alt':")
                    print(f"      Text: '{rating_text1}'")
                    rating_match = re.search(r'(\d+[,.]\d+)', rating_text1.replace(',', '.'))
                    if rating_match:
                        rating_val = float(rating_match.group(1).replace(',', '.'))
                        print(f"      Extracted rating: {rating_val}")
                    else:
                        print(f"      ⚠️  Could not extract numeric rating from text")
                else:
                    print(f"   ❌ Not found with selector '#averageCustomerReviews .a-icon-star .a-icon-alt'")
                
                # Selector 2: .a-icon-star .a-icon-alt (fallback)
                rating_elem2 = soup.select_one('.a-icon-star .a-icon-alt')
                if rating_elem2:
                    rating_text2 = rating_elem2.get_text()
                    print(f"   ✅ Found with selector '.a-icon-star .a-icon-alt':")
                    print(f"      Text: '{rating_text2}'")
                    if not rating_elem1:  # Only show extraction if first selector didn't work
                        rating_match = re.search(r'(\d+[,.]\d+)', rating_text2.replace(',', '.'))
                        if rating_match:
                            rating_val = float(rating_match.group(1).replace(',', '.'))
                            print(f"      Extracted rating: {rating_val}")
                else:
                    print(f"   ❌ Not found with selector '.a-icon-star .a-icon-alt'")
                
                # Check for alternative rating elements
                print(f"\n   🔍 Searching for alternative rating elements:")
                
                # Check for #averageCustomerReviews section
                avg_reviews_section = soup.select_one('#averageCustomerReviews')
                if avg_reviews_section:
                    print(f"   ✅ Found #averageCustomerReviews section")
                    # Look for any star-related elements inside
                    stars_inside = avg_reviews_section.select('.a-icon-star, .a-star, [class*="star"], [data-rating]')
                    if stars_inside:
                        print(f"      Found {len(stars_inside)} star-related elements inside")
                        for i, star in enumerate(stars_inside[:3]):  # Show first 3
                            print(f"      [{i+1}] Tag: {star.name}, Classes: {star.get('class', [])}, Text: '{star.get_text()[:50]}'")
                    else:
                        print(f"      ⚠️  No star-related elements found inside")
                else:
                    print(f"   ❌ #averageCustomerReviews section not found")
                
                # Check for data-rating attributes
                data_rating_elements = soup.select('[data-rating], [data-average-rating], [aria-label*="star"], [aria-label*="rating"]')
                if data_rating_elements:
                    print(f"   ✅ Found {len(data_rating_elements)} elements with rating-related attributes:")
                    for i, elem in enumerate(data_rating_elements[:5]):  # Show first 5
                        attrs = {k: v for k, v in elem.attrs.items() if 'rating' in k.lower() or 'star' in k.lower()}
                        print(f"      [{i+1}] Tag: {elem.name}, Attrs: {attrs}, Text: '{elem.get_text()[:50]}'")
                
                # Check for JSON-LD structured data
                json_scripts = soup.find_all('script', {'type': 'application/ld+json'})
                if json_scripts:
                    print(f"\n   📦 Found {len(json_scripts)} JSON-LD scripts, checking for rating data...")
                    for script in json_scripts:
                        if script.string:
                            try:
                                import json
                                data = json.loads(script.string)
                                if isinstance(data, dict):
                                    # Check for aggregateRating
                                    agg_rating = data.get('aggregateRating', {})
                                    if agg_rating:
                                        rating_val = agg_rating.get('ratingValue')
                                        review_count = agg_rating.get('reviewCount')
                                        if rating_val:
                                            print(f"      ✅ Found rating in JSON-LD: {rating_val} (reviews: {review_count})")
                            except:
                                pass
                
                # Check for review count element
                print(f"\n   📊 Checking review count:")
                review_elem1 = soup.select_one('#acrCustomerReviewText')
                if review_elem1:
                    print(f"   ✅ Found with selector '#acrCustomerReviewText': '{review_elem1.get_text()}'")
                else:
                    print(f"   ❌ Not found with selector '#acrCustomerReviewText'")
                
                review_elem2 = soup.select_one('.a-size-base .a-link-normal')
                if review_elem2:
                    print(f"   ✅ Found with selector '.a-size-base .a-link-normal': '{review_elem2.get_text()}'")
                else:
                    print(f"   ❌ Not found with selector '.a-size-base .a-link-normal'")
                
                # Save HTML snippet for manual inspection (optional)
                if not rating_elem1 and not rating_elem2:
                    print(f"\n   💾 Saving HTML snippet for manual inspection...")
                    # Save a snippet around where rating should be
                    avg_reviews_html = soup.select_one('#averageCustomerReviews')
                    if avg_reviews_html:
                        with open(f"rating_debug_{asin}.html", "w", encoding="utf-8") as f:
                            f.write(str(avg_reviews_html.prettify()))
                        print(f"      Saved to rating_debug_{asin}.html")
                    else:
                        # Save product title area
                        title_area = soup.select_one('#productTitle')
                        if title_area:
                            parent = title_area.find_parent()
                            if parent:
                                with open(f"rating_debug_{asin}.html", "w", encoding="utf-8") as f:
                                    f.write(str(parent.prettify()[:5000]))
                                print(f"      Saved title area to rating_debug_{asin}.html")
        
        except Exception as e:
            print(f"   ❌ Error during HTML analysis: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run tests for all ASINs."""
    print("🧪 Rating Extraction Test Script")
    print("="*80)
    print(f"Testing {len(TEST_ASINS)} ASINs that failed rating extraction\n")
    
    for asin in TEST_ASINS:
        try:
            await test_rating_extraction(asin)
            # Small delay between requests
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error testing {asin}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ Test completed!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

