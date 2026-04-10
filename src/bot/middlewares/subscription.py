"""Subscription check middleware — majburiy obuna tekshirish."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Sequence

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.enums import ChatMemberStatus

from src.db.engine import async_session
from src.db.models import Channel
from src.db.repositories.repos import ChannelRepo
from src.bot.services.redis_service import RedisService
from src.bot.keyboards.inline import subscription_kb
from src.common.config import settings

logger = logging.getLogger("hofiz.middleware.subscription")

ALLOWED_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}


class SubscriptionCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Admin'lar uchun tekshirmaslik
        if user.id in settings.admin_ids:
            return await handler(event, data)

        # Callback "check_sub" bo'lsa, tekshirmaslik (infinite loop bo'lmasligi uchun)
        if isinstance(event, CallbackQuery) and event.data and event.data.startswith(("check_sub", "req_channel")):
            return await handler(event, data)

        # Redis cache tekshirish
        cached = await RedisService.get_sub_status(user.id)
        if cached is True:
            return await handler(event, data)

        bot: Bot = data["bot"]
        async with async_session() as session:
            repo = ChannelRepo(session)
            channels = await repo.get_active()

        if not channels:
            await RedisService.set_sub_status(user.id, True)
            return await handler(event, data)

        # Har bir kanalda a'zolikni tekshirish
        not_subscribed: list[Channel] = []
        for ch in channels:
            try:
                member = await bot.get_chat_member(ch.channel_id, user.id)
                if member.status not in ALLOWED_STATUSES:
                    not_subscribed.append(ch)
            except Exception:
                logger.warning("Cannot check channel %s for user %s", ch.channel_id, user.id)

        if not not_subscribed:
            await RedisService.set_sub_status(user.id, True)
            return await handler(event, data)

        # Obuna bo'lmagan — kanallar ro'yxatini ko'rsatish
        await RedisService.set_sub_status(user.id, False, ttl=300)
        text = (
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgandan so'ng «✅ Obuna bo'ldim» tugmasini bosing."
        )
        if isinstance(event, Message):
            await event.answer(text, reply_markup=subscription_kb(not_subscribed), parse_mode="HTML")
        elif isinstance(event, CallbackQuery) and event.message:
            await event.message.answer(text, reply_markup=subscription_kb(not_subscribed), parse_mode="HTML")
            await event.answer()
        return None
