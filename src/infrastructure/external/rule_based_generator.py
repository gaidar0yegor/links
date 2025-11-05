from .interfaces import IAiRewriter
from ...domain.entities.product import Product


class RuleBasedContentGenerator(IAiRewriter):
    """
    Rule-based content generator - FREE alternative to LLM.

    Uses predefined templates and rules to generate engaging content
    without external API costs.
    """

    def __init__(self):
        self.templates = {
            'electronics': """🛍️ {title}

{description}

💰 Цена: ${price}
⭐ Рейтинг: {rating}/5.0 ({reviews} отзывов)
🔋 Категория: {category}

🎯 Почему купить:
• Высокий рейтинг от покупателей
• Отличное соотношение цена/качество
• Доступно с доставкой

🔗 {affiliate_link}

#электроника #{category_lower} #покупки
""",
            'books': """📚 {title}

{description}

💰 Цена: ${price}
⭐ Рейтинг: {rating}/5.0 ({reviews} отзывов)
📖 Категория: {category}

📖 Отличная книга для:
• Любителей качественной литературы
• Поиск новых знаний и идей
• Коллекционеров интересных изданий

🔗 {affiliate_link}

#книги #{category_lower} #литература
""",
            'home': """🏠 {title}

{description}

💰 Цена: ${price}
⭐ Рейтинг: {rating}/5.0 ({reviews} отзывов)
🏡 Категория: {category}

✨ Преимущества:
• Высокое качество материалов
• Практичное решение для дома
• Отличные отзывы покупателей

🔗 {affiliate_link}

#дом #{category_lower} #товары
""",
            'default': """🛍️ {title}

{description}

💰 Цена: ${price}
⭐ Рейтинг: {rating}/5.0 ({reviews} отзывов)
🏷️ Категория: {category}

🎁 Отличный выбор для покупателей, ценящих качество!

🔗 {affiliate_link}

#покупки #{category_lower} #товары
"""
        }

    def rewrite_description(self, title: str, original_description: str) -> str:
        """
        Simple rule-based description enhancement.
        """
        if not original_description:
            return f"Отличный товар {title} - проверьте характеристики и отзывы!"

        # Basic enhancement rules
        enhanced = original_description

        # Add emojis for better engagement
        if "wireless" in enhanced.lower() or "bluetooth" in enhanced.lower():
            enhanced = "📱 " + enhanced
        elif "premium" in enhanced.lower() or "high quality" in enhanced.lower():
            enhanced = "⭐ " + enhanced

        # Limit length for social media
        if len(enhanced) > 150:
            enhanced = enhanced[:147] + "..."

        return enhanced

    def generate_post_content(self, product: Product) -> str:
        """
        Generate complete post content using templates.
        """
        if not product.affiliate_link:
            raise ValueError("Product must have affiliate link")

        # Select template based on category
        category_lower = product.category.lower()

        if "electronics" in category_lower or "computer" in category_lower:
            template = self.templates['electronics']
        elif "book" in category_lower or "literature" in category_lower:
            template = self.templates['books']
        elif "home" in category_lower or "kitchen" in category_lower:
            template = self.templates['home']
        else:
            template = self.templates['default']

        # Format template with product data
        content = template.format(
            title=product.title,
            description=self.rewrite_description(product.title, product.description or ""),
            price=product.price,
            rating=product.rating,
            reviews=product.review_count,
            category=product.category,
            category_lower=product.category.lower().replace(' ', '').replace('&', 'and'),
            affiliate_link=product.affiliate_link
        )

        return content.strip()
