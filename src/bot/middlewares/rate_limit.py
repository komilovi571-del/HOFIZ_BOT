"""Rate-limit middleware — Redis orqali tezlik cheklash."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.bot.services.redis_service import RedisService


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, max_requests: int = 10, window: int = 60):
        self.max_requests = max_requests
        self.window = window

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        limited = await RedisService.check_rate_limit(
            user.id, self.max_requests, self.window
        )
        if limited:
            if isinstance(event, Message):
                ttl = await RedisService.get_rate_ttl(user.id)
                await event.answer(
                    f"⏱ Iltimos, {ttl} soniya kuting. Juda ko'p so'rov yubordingiz."
                )
            return None

        return await handler(event, data)
