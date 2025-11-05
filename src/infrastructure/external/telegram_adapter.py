import asyncio
from datetime import datetime
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from .interfaces import ITelegramPublisher


class TelegramPublisherAdapter(ITelegramPublisher):
    """
    Telegram Bot API adapter for publishing content.

    Uses python-telegram-bot library to interact with Telegram Bot API.
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)

    async def schedule_post(self, channel_id: str, content: str, scheduled_time: datetime) -> str:
        """
        Schedule a post to Telegram channel.

        Note: Telegram Bot API doesn't support native scheduling.
        In production, this would integrate with a scheduling service or
        use Telegram's built-in scheduling features.

        For MVP, we'll send immediately and return a mock message ID.
        """
        try:
            # Send message immediately (Telegram Bot API doesn't support scheduling)
            # In production, you'd integrate with a job scheduler like APScheduler
            message = await self.bot.send_message(
                chat_id=channel_id,
                text=content,
                parse_mode='HTML',
                disable_web_page_preview=False
            )

            # Return message ID as string
            return str(message.message_id)

        except TelegramError as e:
            raise Exception(f"Failed to send Telegram message: {e}")

    async def send_post_immediately(self, channel_id: str, content: str) -> bool:
        """
        Send post to Telegram channel immediately.
        """
        try:
            await self.bot.send_message(
                chat_id=channel_id,
                text=content,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            return True

        except TelegramError as e:
            print(f"Failed to send Telegram message: {e}")
            return False

    async def validate_channel_access(self, channel_id: str) -> bool:
        """
        Validate that the bot has access to the specified channel.
        """
        try:
            # Try to get chat information
            chat = await self.bot.get_chat(chat_id=channel_id)
            return chat is not None
        except TelegramError:
            return False
