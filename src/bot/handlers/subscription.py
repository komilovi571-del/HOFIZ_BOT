"""Obuna tizimi handleri — majburiy obuna tekshirish va boshqarish."""

from __future__ import annotations

import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from aiogram.enums import ChatMemberStatus

from src.db.engine import async_session
from src.db.repositories.repos import ChannelRepo, ChannelRequestRepo, UserRepo
from src.bot.services.redis_service import RedisService
from src.bot.keyboards.inline import subscription_kb

logger = logging.getLogger("hofiz.handler.subscription")
router = Router(name="subscription")

ALLOWED_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}


@router.callback_query(lambda c: c.data == "check_sub")
async def check_subscription(callback: CallbackQuery, bot: Bot):
    """'Obuna bo'ldim' tugmasi — qayta tekshirish."""
    user_id = callback.from_user.id

    async with async_session() as session:
        repo = ChannelRepo(session)
        channels = await repo.get_active()

    if not channels:
        await RedisService.set_sub_status(user_id, True)
        await callback.answer("✅ Barcha kanallar tekshirildi!", show_alert=True)
        if callback.message:
            await callback.message.delete()
        return

    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status not in ALLOWED_STATUSES:
                not_subscribed.append(ch)
        except Exception:
            logger.warning("Cannot check channel %s", ch.channel_id)

    if not not_subscribed:
        await RedisService.set_sub_status(user_id, True)
        await RedisService.invalidate_sub(user_id)
        await callback.answer("✅ Rahmat! Endi botdan foydalanishingiz mumkin!", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                "✅ <b>Obuna tasdiqlandi!</b>\n\n"
                "Endi menga link yuboring yoki audio/ovoz yuboring! ⚡️",
                parse_mode="HTML",
            )
    else:
        await callback.answer(
            f"❌ Hali {len(not_subscribed)} ta kanalga obuna bo'lmadingiz!",
            show_alert=True,
        )
        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=subscription_kb(not_subscribed)
            )


@router.callback_query(lambda c: c.data and c.data.startswith("req_channel:"))
async def request_channel_access(callback: CallbackQuery, bot: Bot):
    """So'rovli kanal — obunaga so'rov yuborish."""
    channel_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with async_session() as session:
        user_repo = UserRepo(session)
        db_user = await user_repo.get_by_telegram_id(user_id)
        if not db_user:
            await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
            return

        ch_repo = ChannelRepo(session)
        channel = await ch_repo.get_by_channel_id(channel_id)
        if not channel:
            await callback.answer("❌ Kanal topilmadi.", show_alert=True)
            return

        req_repo = ChannelRequestRepo(session)

        # Mavjud so'rov borligini tekshirish
        existing = await req_repo.get_pending(channel.id)
        user_has_pending = any(r.user_id == db_user.id for r in existing)
        if user_has_pending:
            await callback.answer("⏳ So'rovingiz allaqachon yuborilgan. Kuting.", show_alert=True)
            return

        # So'rov yaratish
        await req_repo.create(user_id=db_user.id, channel_id=channel.id)

    await callback.answer(
        "📨 So'rov yuborildi! Admin tasdiqlashi kutilmoqda.",
        show_alert=True,
    )

    # Admin'larga xabar berish
    from src.common.config import settings
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"📨 <b>Yangi kanal so'rovi</b>\n\n"
                f"👤 {callback.from_user.full_name} (ID: <code>{user_id}</code>)\n"
                f"📺 Kanal: {channel.title}\n\n"
                f"Admin paneldan tasdiqlang.",
                parse_mode="HTML",
            )
        except Exception:
            pass
