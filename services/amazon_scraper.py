#!/usr/bin/env python3
"""
Amazon Product Page Web Scraper
Falls back to scraping when PA API doesn't provide price/rating/review/sales rank data.
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
import re
from services.logger import bot_logger


class AmazonProductScraper:
    """Web scraper for Amazon product data when API is insufficient."""

    def __init__(self):
        self.base_url = "https://www.amazon.it"
        self.session = None
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def scrape_product_data(self, asin: str) -> Optional[Dict[str, Any]]:
        """
        Scrape product data from Amazon product page.

        Args:
            asin: Amazon product ASIN

        Returns:
            Dictionary with scraped product data or None if failed
        """
        # Check cache first
        cache_key = f"product_{asin}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if asyncio.get_event_loop().time() - timestamp < self.cache_ttl:
                print(f"DEBUG: Using cached data for ASIN {asin}")
                return cached_data

        try:
            url = f"{self.base_url}/dp/{asin}"
            print(f"DEBUG: Scraping product page: {url}")

            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    print(f"DEBUG: Failed to fetch page for ASIN {asin}, status: {response.status}")
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                product_data = {
                    'asin': asin,
                    'price': None,
                    'currency': 'EUR',
                    'rating': None,
                    'review_count': None,
                    'sales_rank': None,
                    'title': None,
                    'features': [],
                    'description': None
                }

                # Extract price
                product_data.update(self._extract_price(soup))

                # Extract rating and reviews
                product_data.update(self._extract_rating_reviews(soup))

                # Extract sales rank
                product_data.update(self._extract_sales_rank(soup))

                # Extract title
                product_data.update(self._extract_title(soup))

                # Extract features/description
                product_data.update(self._extract_features(soup))

                # Cache the result
                self.cache[cache_key] = (product_data, asyncio.get_event_loop().time())

                # print(f"DEBUG: Scraped data for ASIN {asin}: price={product_data['price']}, rating={product_data['rating']}, reviews={product_data['review_count']}, sales_rank={product_data['sales_rank']}")

                return product_data

        except Exception as e:
            print(f"DEBUG: Failed to scrape product {asin}: {e}")
            bot_logger.log_error("AmazonScraper", e, f"Failed to scrape product {asin}")
            return None

    def _extract_price(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract price from product page - enhanced for Amazon Italy."""
        try:
            # Amazon Italy specific price selectors (most common first)
            price_selectors = [
                # Core price selectors
                '#corePrice_feature_div .a-price .a-offscreen',
                '#corePrice_desktop .a-price .a-offscreen',
                '#corePriceDisplay_desktop_feature_div .a-price .a-offscreen',

                # Buybox prices
                '#price_inside_buybox',
                '#newBuyBoxPrice',
                '#buyNewSection .a-color-price',

                # Deal/listing prices
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                '#priceblock_saleprice',

                # General price selectors
                '.a-price .a-offscreen',
                '.a-color-price',
                '#snsPrice',

                # Kindle/universal price
                '#kindle-price',

                # Used/refurbished prices
                '#usedBuySection .a-color-price',
                '#refurbishedBuySection .a-color-price'
            ]

            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text().strip()
                    # print(f"DEBUG: Found price element with selector '{selector}': '{price_text}'")

                    # Extract numeric price - handle both EUR and other formats
                    # Look for patterns like: €29,99 or 29,99 € or 29.99
                    price_patterns = [
                        r'€\s*(\d+[,.]\d+)',  # €29,99
                        r'(\d+[,.]\d+)\s*€',  # 29,99 €
                        r'(\d+[,.]\d+)',      # 29.99 or 29,99
                    ]

                    for pattern in price_patterns:
                        price_match = re.search(pattern, price_text.replace(' ', ''))
                        if price_match:
                            price_str = price_match.group(1)
                            # Convert European decimal format (comma) to dot
                            price_clean = price_str.replace(',', '.')
                            try:
                                price = float(price_clean)
                                # print(f"DEBUG: Successfully extracted price: €{price}")
                                return {'price': price, 'currency': 'EUR'}
                            except ValueError:
                                continue

            # Try to find price in JSON-LD structured data
            json_scripts = soup.find_all('script', {'type': 'application/ld+json'})
            for script in json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict):
                            # Check for offers/price in JSON-LD
                            offers = data.get('offers', [])
                            if isinstance(offers, list) and offers:
                                offer = offers[0] if isinstance(offers[0], dict) else offers
                                if isinstance(offer, dict):
                                    price_val = offer.get('price')
                                    if price_val:
                                        try:
                                            price = float(str(price_val).replace(',', '.'))
                                            # print(f"DEBUG: Found price in JSON-LD: €{price}")
                                            return {'price': price, 'currency': 'EUR'}
                                        except (ValueError, TypeError):
                                            continue
                            elif isinstance(offers, dict):
                                price_val = offers.get('price')
                                if price_val:
                                    try:
                                        price = float(str(price_val).replace(',', '.'))
                                        # print(f"DEBUG: Found price in JSON-LD: €{price}")
                                        return {'price': price, 'currency': 'EUR'}
                                    except (ValueError, TypeError):
                                        continue
                    except (json.JSONDecodeError, TypeError):
                        continue

            # Try to find price in JavaScript variables
            scripts = soup.find_all('script', {'type': 'text/javascript'})
            for script in scripts:
                if script.string:
                    # Look for common price variable patterns
                    price_vars = [
                        r'"price":\s*"([^"]+)"',
                        r'price["\']\s*:\s*["\']([^"\']+)["\']',
                        r'amount["\']\s*:\s*["\']([^"\']+)["\']',
                    ]

                    for pattern in price_vars:
                        matches = re.findall(pattern, script.string)
                        for match in matches:
                            try:
                                # Try to extract numeric part
                                price_match = re.search(r'(\d+[,.]\d+)', match.replace(',', '.'))
                                if price_match:
                                    price = float(price_match.group(1).replace(',', '.'))
                                    # print(f"DEBUG: Found price in JavaScript: €{price}")
                                    return {'price': price, 'currency': 'EUR'}
                            except (ValueError, TypeError):
                                continue

            # print("DEBUG: No price found with any method")

        except Exception as e:
            print(f"DEBUG: Failed to extract price: {e}")

        return {'price': None, 'currency': 'EUR'}

    def _extract_rating_reviews(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract rating and review count."""
        try:
            # Look for rating
            rating_element = soup.select_one('#averageCustomerReviews .a-icon-star .a-icon-alt')
            if not rating_element:
                rating_element = soup.select_one('.a-icon-star .a-icon-alt')

            rating = None
            if rating_element:
                rating_text = rating_element.get_text()
                rating_match = re.search(r'(\d+[,.]\d+)', rating_text.replace(',', '.'))
                if rating_match:
                    rating = float(rating_match.group(1).replace(',', '.'))

            # Look for review count
            review_element = soup.select_one('#acrCustomerReviewText')
            if not review_element:
                review_element = soup.select_one('.a-size-base .a-link-normal')

            review_count = None
            if review_element:
                review_text = review_element.get_text()
                review_match = re.search(r'(\d+(?:[.,]\d+)*)', review_text.replace(',', '').replace('.', ''))
                if review_match:
                    review_count = int(review_match.group(1).replace(',', '').replace('.', ''))

            # If no reviews found, rating cannot be valid (avoids false positives from ads/recommendations)
            if not review_count:
                rating = None

            return {'rating': rating, 'review_count': review_count}

        except Exception as e:
            print(f"DEBUG: Failed to extract rating/reviews: {e}")

        return {'rating': None, 'review_count': None}

    def _extract_sales_rank(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract sales rank (best seller rank)."""
        try:
            # Look for sales rank in product details
            sales_rank_patterns = [
                r'#(\d+(?:[.,]\d+)*) in ([^<]+)',
                r'(\d+(?:[.,]\d+)*) in ([^<]+)',
                r'Classifica Bestseller: #(\d+(?:[.,]\d+)*)'
            ]

            # Search in text content
            text_content = soup.get_text()
            for pattern in sales_rank_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    rank_str = match.group(1)
                    rank = int(rank_str.replace(',', '').replace('.', ''))
                    return {'sales_rank': rank}

            # Look for sales rank in specific elements
            rank_elements = soup.select('.zg_hrsr_item .zg_hrsr_rank')
            for element in rank_elements:
                rank_text = element.get_text()
                rank_match = re.search(r'#(\d+)', rank_text)
                if rank_match:
                    rank = int(rank_match.group(1))
                    return {'sales_rank': rank}

        except Exception as e:
            print(f"DEBUG: Failed to extract sales rank: {e}")

        return {'sales_rank': None}

    def _extract_title(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract product title."""
        try:
            title_element = soup.select_one('#productTitle')
            if not title_element:
                title_element = soup.select_one('.product-title-word-break')

            if title_element:
                title = title_element.get_text().strip()
                return {'title': title}

        except Exception as e:
            print(f"DEBUG: Failed to extract title: {e}")

        return {'title': None}

    def _extract_features(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract product features and description."""
        try:
            features = []

            # Extract bullet points
            bullet_elements = soup.select('#feature-bullets .a-list-item')
            for bullet in bullet_elements:
                text = bullet.get_text().strip()
                if text:
                    features.append(text)

            # Extract product description
            desc_element = soup.select_one('#productDescription')
            if not desc_element:
                desc_element = soup.select_one('.product-description-content-text')

            description = None
            if desc_element:
                description = desc_element.get_text().strip()

            return {
                'features': features[:5],  # Limit to first 5 features
                'description': description
            }

        except Exception as e:
            print(f"DEBUG: Failed to extract features: {e}")

        return {'features': [], 'description': None}

    async def enrich_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich product data with scraped information if API data is missing.

        Args:
            product_data: Product data from API (may have None values)

        Returns:
            Enriched product data with scraped fallback data
        """
        enriched_data = product_data.copy()
        asin = product_data.get('asin')

        if not asin:
            return enriched_data

        # Check if we need to scrape (if key data is missing)
        needs_scraping = (
            product_data.get('price') is None or
            product_data.get('rating') is None or
            product_data.get('review_count') is None or
            product_data.get('sales_rank') is None
        )

        if needs_scraping:
            # print(f"DEBUG: Missing data for ASIN {asin}, attempting to scrape...")
            scraped_data = await self.scrape_product_data(asin)

            if scraped_data:
                # Fill in missing data with scraped data
                for key in ['price', 'rating', 'review_count', 'sales_rank', 'title', 'features', 'description']:
                    if enriched_data.get(key) is None and scraped_data.get(key) is not None:
                        enriched_data[key] = scraped_data[key]
                        # print(f"DEBUG: Filled missing {key} for ASIN {asin}: {scraped_data[key]}")
            
            print(f"DEBUG: Enriched ASIN {asin} via scraping: Price={enriched_data.get('price')}, Rating={enriched_data.get('rating')}, Reviews={enriched_data.get('review_count')}")

        return enriched_data


# Global scraper instance
_amazon_scraper = None

async def get_amazon_scraper() -> AmazonProductScraper:
    """Get global Amazon scraper instance."""
    global _amazon_scraper
    if _amazon_scraper is None:
        _amazon_scraper = AmazonProductScraper()
    return _amazon_scraper

async def enrich_product_with_scraping(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to enrich product data with web scraping.

    Args:
        product_data: Product data that may need enrichment

    Returns:
        Enriched product data
    """
    async with AmazonProductScraper() as scraper:
        return await scraper.enrich_product_data(product_data)
