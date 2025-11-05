import asyncio
from typing import Optional
from openai import AsyncOpenAI

from .interfaces import IAiRewriter
from ...domain.entities.product import Product


class OpenAiRewriterAdapter(IAiRewriter):
    """
    OpenAI GPT integration for content rewriting.

    Uses GPT-4 for rewriting product descriptions and generating content.
    """

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def rewrite_description(self, title: str, original_description: str) -> str:
        """
        Rewrite product description using AI for better engagement.
        """
        prompt = f"""
        Rewrite the following product description to make it more engaging and persuasive for social media.
        Keep it concise (2-3 sentences) but highlight the key benefits.
        Use natural, conversational language that would appeal to potential buyers.

        Product Title: {title}
        Original Description: {original_description}

        Rewritten description:
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional copywriter specializing in product descriptions for social media marketing."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )

            rewritten = response.choices[0].message.content.strip()
            return rewritten if rewritten else original_description

        except Exception as e:
            print(f"OpenAI API error: {e}")
            return original_description  # Fallback to original

    async def generate_post_content(self, product: Product) -> str:
        """
        Generate complete post content for Telegram including rewritten description.
        """
        if not product.affiliate_link:
            raise ValueError("Product must have affiliate link")

        # First rewrite the description
        rewritten_description = await self.rewrite_description(
            product.title,
            product.description or "High-quality product with excellent features."
        )

        # Generate engaging post content
        prompt = f"""
        Create an engaging Telegram post for this product. Include:
        - Catchy emoji and title
        - Rewritten description (use the one provided)
        - Key specs (price, rating, reviews)
        - Call-to-action with affiliate link
        - Relevant hashtags

        Product details:
        - Title: {product.title}
        - Rewritten description: {rewritten_description}
        - Price: ${product.price}
        - Rating: {product.rating}/5.0
        - Reviews: {product.review_count}
        - Category: {product.category}
        - Best Seller: {"Yes" if product.is_best_seller else "No"}

        Format for Telegram with emojis and proper structure:
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a social media marketing expert creating viral Telegram posts for affiliate products."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.8
            )

            post_content = response.choices[0].message.content.strip()

            # Ensure affiliate link is included
            if product.affiliate_link not in post_content:
                post_content += f"\n\n🔗 {product.affiliate_link}"

            return post_content

        except Exception as e:
            print(f"OpenAI API error: {e}")
            # Fallback to basic format
            return self._create_basic_post(product, rewritten_description)

    def _create_basic_post(self, product: Product, description: str) -> str:
        """Fallback method to create basic post content."""
        return f"""🛍️ {product.title}

{description}

💰 Price: ${product.price}
⭐ Rating: {product.rating}/5.0 ({product.review_count} reviews)
🏷️ Category: {product.category}

🔗 {product.affiliate_link}

#shopping #{product.category.replace(' ', '').replace('&', 'and')}
"""
