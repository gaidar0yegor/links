#!/usr/bin/env python3
"""
Content Generator Service for Telegram Affiliate Bot
Handles content generation using Google Sheets templates and AI rewriting.
"""

import random
from typing import Dict, List, Optional, Any
from services.sheets_api import sheets_api
from services.llm_client import GeminiClient
from services.logger import bot_logger


class ContentGenerator:
    """Service for generating affiliate content using templates and AI."""

    def __init__(self):
        self.llm_client = GeminiClient()
        self.templates_cache = {}
        self.hashtags_cache = {}
        self._load_templates()

    def _load_templates(self):
        """Load content templates and hashtags from Google Sheets."""
        try:
            # Load content templates
            templates_data = sheets_api.get_sheet_data('content_templates')
            if templates_data and len(templates_data) > 1:
                headers = templates_data[0]
                col_indices = {header: idx for idx, header in enumerate(headers)}

                self.templates_cache = {}
                for row in templates_data[1:]:
                    if len(row) >= len(headers):
                        template_id = row[col_indices.get('template_id', 0)]
                        category = row[col_indices.get('category', 4)]
                        template_text = row[col_indices.get('template_text', 2)]
                        hashtags = row[col_indices.get('hashtags', 3)]

                        if category not in self.templates_cache:
                            self.templates_cache[category] = []

                        self.templates_cache[category].append({
                            'id': template_id,
                            'text': template_text,
                            'hashtags': hashtags
                        })

            # Load hashtags
            hashtags_data = sheets_api.get_sheet_data('hashtags')
            if hashtags_data and len(hashtags_data) > 1:
                headers = hashtags_data[0]
                col_indices = {header: idx for idx, header in enumerate(headers)}

                self.hashtags_cache = {}
                for row in hashtags_data[1:]:
                    if len(row) >= len(headers):
                        category = row[col_indices.get('category', 0)]
                        hashtags_list = row[col_indices.get('hashtags_list', 1)]
                        self.hashtags_cache[category] = hashtags_list

            bot_logger.log_info("ContentGenerator", f"Loaded {len(self.templates_cache)} template categories and {len(self.hashtags_cache)} hashtag sets")

        except Exception as e:
            bot_logger.log_error("ContentGenerator", e, "Failed to load templates from Google Sheets")
            self.templates_cache = {}
            self.hashtags_cache = {}

    def get_random_template(self, category: str) -> Optional[Dict[str, str]]:
        """Get a random template for the specified category."""
        if category not in self.templates_cache:
            # Try to find a generic template or fallback
            if 'Electronics' in self.templates_cache:
                category = 'Electronics'
            else:
                return None

        templates = self.templates_cache[category]
        if not templates:
            return None

        return random.choice(templates)

    def get_hashtags_for_category(self, category: str) -> str:
        """Get hashtags for the specified category."""
        return self.hashtags_cache.get(category, '#Affiliate #Product')

    def generate_content(self, product_data: Dict[str, Any], category: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate content for a product using templates and AI rewriting.

        Args:
            product_data: Product information dictionary
            category: Product category (optional, will be inferred from product_data)

        Returns:
            Dictionary with 'content' and 'hashtags' keys
        """
        try:
            # Determine category
            if not category:
                category = product_data.get('category', 'Electronics')

            # Get template
            template = self.get_random_template(category)
            if not template:
                bot_logger.log_error("ContentGenerator", Exception(f"No template found for category: {category}"), "Using fallback template")
                template = {
                    'text': 'Check out this amazing {product_name}! ⭐ {rating}/5 stars from {reviews_count} reviews. Get yours now: {affiliate_link} {hashtags}',
                    'hashtags': '#Product #Affiliate'
                }

            # Fill template variables
            content = template['text'].format(
                product_name=product_data.get('name', 'Product'),
                rating=product_data.get('rating', '4.5'),
                reviews_count=product_data.get('reviews_count', '100'),
                affiliate_link=product_data.get('affiliate_link', '#'),
                hashtags=template.get('hashtags', '')
            )

            # Get category-specific hashtags
            category_hashtags = self.get_hashtags_for_category(category)

            # Combine template hashtags with category hashtags
            all_hashtags = f"{template.get('hashtags', '')} {category_hashtags}".strip()

            # Use AI to rewrite the content if available
            try:
                rewritten_content = self._rewrite_content(content)
                if rewritten_content:
                    content = rewritten_content
            except Exception as e:
                bot_logger.log_error("ContentGenerator", e, "AI rewriting failed, using original content")

            return {
                'content': content,
                'hashtags': all_hashtags,
                'template_id': template.get('id', 'fallback'),
                'category': category
            }

        except Exception as e:
            bot_logger.log_error("ContentGenerator", e, f"Content generation failed for product: {product_data.get('name', 'Unknown')}")
            return None

    def _rewrite_content(self, content: str) -> Optional[str]:
        """Use AI to rewrite content for better engagement."""
        try:
            # Get rewrite prompt from Google Sheets
            rewrite_prompt_data = sheets_api.get_sheet_data('rewrite_prompt')
            if rewrite_prompt_data and len(rewrite_prompt_data) > 1:
                prompt = rewrite_prompt_data[1][0]  # First row, first column
            else:
                prompt = "Rewrite the following text to make it engaging and persuasive and fit for a social media post."

            full_prompt = f"{prompt}\n\n{content}"

            rewritten = self.llm_client.rewrite_text(prompt, content)
            return rewritten if rewritten else content

        except Exception as e:
            bot_logger.log_error("ContentGenerator", e, "AI content rewriting failed")
            return content

    def generate_post_content(self, product_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Generate complete post content including text, hashtags, and metadata.

        Args:
            product_data: Product information from Amazon/Google Sheets

        Returns:
            Complete post data dictionary
        """
        content_result = self.generate_content(product_data)

        if not content_result:
            return None

        # Add additional metadata
        post_data = {
            'text': content_result['content'],
            'hashtags': content_result['hashtags'],
            'product_name': product_data.get('name', ''),
            'product_link': product_data.get('affiliate_link', ''),
            'product_image': product_data.get('image_url', ''),
            'rating': product_data.get('rating', ''),
            'reviews_count': product_data.get('reviews_count', ''),
            'category': content_result['category'],
            'template_id': content_result['template_id']
        }

        return post_data


# Global instance
content_generator = ContentGenerator()
