"""Logging middleware — har bir update'ni log qiladi."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger("hofiz.middleware.logging")


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_info = f"user={user.id}" if user else "user=unknown"
        logger.debug("Update: %s | %s", type(event).__name__, user_info)
        return await handler(event, data)
