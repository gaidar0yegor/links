import asyncio
import random
from typing import List
from .interfaces import IPartnerApi
from ...domain.entities.product import Product


class AmazonPartnerApiAdapter(IPartnerApi):
    """
    Amazon Product Advertising API v5.0 adapter.

    In production, this would integrate with actual Amazon PA API.
    For MVP, this is a mock implementation with sample data.
    """

    def __init__(self, access_key: str, secret_key: str, associate_tag: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.associate_tag = associate_tag
        self.base_url = "https://webservices.amazon.com/paapi5"

    async def get_available_categories(self) -> List[str]:
        """Get list of available product categories."""
        # Mock categories - in real implementation would call Amazon API
        return [
            "Electronics", "Books", "Home & Kitchen", "Sports & Outdoors",
            "Beauty & Personal Care", "Toys & Games", "Fashion", "Automotive",
            "Health & Household", "Office Products"
        ]

    async def fetch_products(self, categories: List[str], limit: int = 100) -> List[Product]:
        """
        Fetch products from Amazon based on categories.

        In production, this would use Amazon PA API SearchItems operation.
        """
        # Mock implementation - generate sample products
        products = []

        # Sample product templates
        product_templates = [
            {
                "title": "Wireless Bluetooth Headphones with Noise Cancellation",
                "description": "Premium wireless headphones with active noise cancellation, 30-hour battery life, and superior sound quality.",
                "price": 199.99,
                "rating": 4.5,
                "reviews": 1250,
                "image_url": "https://example.com/headphones.jpg",
                "is_best_seller": True
            },
            {
                "title": "Smart Fitness Tracker Watch",
                "description": "Advanced fitness tracker with heart rate monitoring, GPS, sleep tracking, and 7-day battery life.",
                "price": 149.99,
                "rating": 4.3,
                "reviews": 890,
                "image_url": "https://example.com/watch.jpg",
                "is_best_seller": False
            },
            {
                "title": "Professional Coffee Maker Machine",
                "description": "Programmable coffee maker with thermal carafe, brew strength control, and 12-cup capacity.",
                "price": 89.99,
                "rating": 4.7,
                "reviews": 2100,
                "image_url": "https://example.com/coffee.jpg",
                "is_best_seller": True
            },
            {
                "title": "Ergonomic Office Chair",
                "description": "Adjustable ergonomic chair with lumbar support, breathable mesh, and 300lb weight capacity.",
                "price": 299.99,
                "rating": 4.4,
                "reviews": 567,
                "image_url": "https://example.com/chair.jpg",
                "is_best_seller": False
            },
            {
                "title": "Portable Power Bank 20000mAh",
                "description": "High-capacity power bank with fast charging, multiple USB ports, and LED power indicator.",
                "price": 39.99,
                "rating": 4.2,
                "reviews": 3400,
                "image_url": "https://example.com/powerbank.jpg",
                "is_best_seller": True
            }
        ]

        # Generate products based on requested categories
        for i in range(min(limit, 50)):  # Limit to 50 for demo
            template = random.choice(product_templates)
            category = random.choice(categories) if categories else "Electronics"

            product = Product(
                channel_id=0,  # Will be set by use case
                source_id=f"AMZN{random.randint(1000000, 9999999)}",
                title=template["title"],
                description=template["description"],
                image_url=template["image_url"],
                price=template["price"],
                rating=template["rating"],
                review_count=template["reviews"],
                category=category,
                is_best_seller=template["is_best_seller"]
            )
            products.append(product)

            # Simulate API delay
            await asyncio.sleep(0.01)

        return products

    async def generate_affiliate_link(self, product_source_id: str) -> str:
        """
        Generate affiliate link for a product.

        In production, this would use Amazon's affiliate link format.
        """
        # Mock affiliate link generation
        # Real implementation would construct proper Amazon affiliate URL
        base_url = "https://www.amazon.com/dp/"
        affiliate_params = f"?tag={self.associate_tag}"

        # Extract ASIN from source_id (mock)
        asin = product_source_id.replace("AMZN", "B0") + "EXAMPLE"
        affiliate_link = f"{base_url}{asin}{affiliate_params}"

        # Simulate API call delay
        await asyncio.sleep(0.05)

        return affiliate_link
