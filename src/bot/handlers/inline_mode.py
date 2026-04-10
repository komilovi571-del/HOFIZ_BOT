"""Inline mode handleri — to'liq inline rejim qo'llab-quvvatlashi."""

from __future__ import annotations

import hashlib
import logging

from aiogram import Router, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultVideo,
    InlineQueryResultPhoto,
    InputTextMessageContent,
    ChosenInlineResult,
)

from src.bot.filters.filters import detect_platform, PLATFORM_EMOJI
from src.bot.services.download_service import download_service
from src.bot.services.redis_service import RedisService

logger = logging.getLogger("hofiz.handler.inline")
router = Router(name="inline_mode")


@router.inline_query()
async def handle_inline_query(query: InlineQuery, bot: Bot):
    """Inline so'rov — URL yoki qo'shiq qidirish."""
    text = query.query.strip()
    results = []

    if not text:
        # Bo'sh so'rov — yordamchi xabar
        results.append(
            InlineQueryResultArticle(
                id="help",
                title="📥 Media yuklab olish",
                description="Instagram, TikTok, Snapchat, Likee, Pinterest linkini yozing",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        "⚡️ <b>HOFIZ BOT — Media Yuklab Olish</b>\n\n"
                        "Qo'llab-quvvatlanadigan platformalar:\n"
                        "📸 Instagram | 🎵 TikTok | 👻 Snapchat\n"
                        "❤️ Likee | 📌 Pinterest\n\n"
                        "🔍 Inline: <code>@hofiz_bot link</code>"
                    ),
                    parse_mode="HTML",
                ),
            )
        )
        results.append(
            InlineQueryResultArticle(
                id="shazam_help",
                title="🎵 Musiqa aniqlash",
                description="Botga ovozli xabar yuboring — qo'shiqni aniqlayman",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        "🎵 <b>Musiqa aniqlash (Shazam)</b>\n\n"
                        "Botga bevosita yuboring:\n"
                        "🎤 Ovozli xabar | 🎵 Audio | 🎬 Video | 📹 Video xabar\n\n"
                        "⚡️ @hofiz_bot"
                    ),
                    parse_mode="HTML",
                ),
            )
        )
        await query.answer(results, cache_time=300, is_personal=False)
        return

    # URL bo'lsa — platformani aniqlash
    platform = detect_platform(text)
    if platform:
        # Cache tekshirish
        cached = await RedisService.get_inline_cache(text)
        if cached:
            await query.answer(
                [_dict_to_inline_result(r) for r in cached[:10]],
                cache_time=300,
                is_personal=False,
            )
            return

        emoji = PLATFORM_EMOJI.get(platform, "📥")

        # Ma'lumot olish (yuklamasdan)
        try:
            info = await download_service.get_info(text, platform)
            title = info.get("title", f"{platform.title()} media")
            author = info.get("author", "")
            thumbnail_url = info.get("thumbnail", "")

            description = f"👤 {author}" if author else f"{platform.title()}'dan yuklab olish"

            if thumbnail_url:
                results.append(
                    InlineQueryResultArticle(
                        id=hashlib.md5(text.encode()).hexdigest(),
                        title=f"{emoji} {title[:64]}",
                        description=description,
                        thumbnail_url=thumbnail_url,
                        input_message_content=InputTextMessageContent(
                            message_text=(
                                f"{emoji} <b>{platform.title()} — yuklab olish</b>\n"
                                f"📝 {title[:200]}\n"
                                f"{'👤 @' + author if author else ''}\n\n"
                                f"🔗 {text}\n"
                                f"⚡️ @hofiz_bot orqali yuklab oling!"
                            ),
                            parse_mode="HTML",
                        ),
                    )
                )
            else:
                results.append(
                    InlineQueryResultArticle(
                        id=hashlib.md5(text.encode()).hexdigest(),
                        title=f"{emoji} {title[:64]}",
                        description=description,
                        input_message_content=InputTextMessageContent(
                            message_text=(
                                f"{emoji} <b>{platform.title()} — yuklab olish</b>\n"
                                f"🔗 {text}\n\n"
                                f"⚡️ @hofiz_bot orqali yuklab oling!"
                            ),
                            parse_mode="HTML",
                        ),
                    )
                )
        except Exception as e:
            logger.warning("Inline info error: %s", e)
            results.append(
                InlineQueryResultArticle(
                    id=hashlib.md5(text.encode()).hexdigest(),
                    title=f"{emoji} {platform.title()}'dan yuklab olish",
                    description=text[:64],
                    input_message_content=InputTextMessageContent(
                        message_text=(
                            f"{emoji} <b>{platform.title()} media</b>\n"
                            f"🔗 {text}\n\n"
                            f"⚡️ Yuklab olish uchun @hofiz_bot ga yuboring"
                        ),
                        parse_mode="HTML",
                    ),
                )
            )
    else:
        # URL emas — qo'shiq qidirish sifatida
        results.append(
            InlineQueryResultArticle(
                id=hashlib.md5(text.encode()).hexdigest(),
                title=f"🔍 Qidirish: {text[:50]}",
                description="Bot'ga yuboring — musiqa aniqlash uchun",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"🔍 <b>Qidiruv:</b> {text}\n\n"
                        f"🎵 Musiqa aniqlash uchun @hofiz_bot ga audio/ovoz yuboring\n"
                        f"📥 Media yuklab olish uchun link yuboring"
                    ),
                    parse_mode="HTML",
                ),
            )
        )

    await query.answer(results, cache_time=60, is_personal=False)


@router.chosen_inline_result()
async def handle_chosen_result(chosen: ChosenInlineResult):
    """Foydalanuvchi inline natijani tanlagan — statistikaga yozish."""
    await RedisService.incr_stat("inline_chosen")
    logger.info("Inline chosen: user=%s, result=%s", chosen.from_user.id, chosen.result_id)


def _dict_to_inline_result(d: dict) -> InlineQueryResultArticle:
    """Dict dan InlineQueryResult yaratish (cache uchun)."""
    return InlineQueryResultArticle(
        id=d.get("id", "cached"),
        title=d.get("title", ""),
        description=d.get("description", ""),
        input_message_content=InputTextMessageContent(
            message_text=d.get("message_text", ""),
            parse_mode="HTML",
        ),
    )
