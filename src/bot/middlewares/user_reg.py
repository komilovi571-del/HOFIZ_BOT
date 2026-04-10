"""User registration middleware — yangi foydalanuvchilarni avtomatik ro'yxatdan o'tkazadi."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.db.engine import async_session
from src.db.repositories.repos import UserRepo
from src.bot.services.redis_service import RedisService


class UserRegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        async with async_session() as session:
            repo = UserRepo(session)
            db_user, is_new = await repo.get_or_create(
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name or "",
            )

            if db_user.is_banned:
                return None

            data["db_user"] = db_user
            data["db_session"] = session
            data["is_new_user"] = is_new

            if is_new:
                await RedisService.incr_stat("new_users")

            await RedisService.incr_stat("active_users")
            return await handler(event, data)
