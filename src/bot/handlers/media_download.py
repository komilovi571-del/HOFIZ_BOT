"""Media yuklab olish handleri — URL qabul qilish va media yuborish."""

from __future__ import annotations

import logging
import os

from aiogram import Router, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery

from src.bot.filters.filters import IsSupportedURL
from src.bot.services.download_service import download_service
from src.bot.services.redis_service import RedisService
from src.bot.keyboards.inline import download_result_kb
from src.api.processors.ffmpeg import cleanup
from src.common.exceptions import DownloadError

logger = logging.getLogger("hofiz.handler.download")
router = Router(name="media_download")

PLATFORM_EMOJI = {
    "instagram": "📸",
    "tiktok": "🎵",
    "snapchat": "👻",
    "likee": "❤️",
    "pinterest": "📌",
}


@router.message(IsSupportedURL())
async def handle_media_url(
    message: Message, bot: Bot, platform: str, url: str, db_user=None
):
    """Foydalanuvchi media URL yuborsa — yuklab berish."""
    emoji = PLATFORM_EMOJI.get(platform, "📥")

    # 1. Cache tekshirish — oldin yuklangan bo'lsa tezkor javob
    cached_file_id = await RedisService.get_cached_file_id(url)
    if cached_file_id:
        try:
            if "|video" in cached_file_id:
                fid = cached_file_id.replace("|video", "")
                await message.answer_video(fid, caption=f"{emoji} Tayyor! (keshdan)")
            elif "|photo" in cached_file_id:
                fid = cached_file_id.replace("|photo", "")
                await message.answer_photo(fid, caption=f"{emoji} Tayyor! (keshdan)")
            elif "|audio" in cached_file_id:
                fid = cached_file_id.replace("|audio", "")
                await message.answer_audio(fid, caption=f"{emoji} Tayyor! (keshdan)")
            else:
                await message.answer_document(cached_file_id, caption=f"{emoji} Tayyor! (keshdan)")
            await RedisService.incr_stat("downloads")
            return
        except Exception:
            await RedisService.delete(f"dl:{RedisService.url_hash(url)}")

    # 2. Progress xabari
    progress_msg = await message.answer(
        f"{emoji} <b>{platform.title()}</b>'dan yuklanmoqda...\n"
        "⏳ Iltimos, kuting...",
        parse_mode="HTML",
    )

    # 3. API ga yuklab olish so'rovi
    try:
        result = await download_service.download(url, platform)
    except DownloadError as e:
        await progress_msg.edit_text(f"❌ Yuklab olish muvaffaqiyatsiz:\n{e}")
        return
    except Exception as e:
        logger.exception("Download handler error: %s", e)
        await progress_msg.edit_text("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    # 4. Natijani foydalanuvchiga yuborish
    file_path = result.get("file_path")
    audio_path = result.get("audio_path")
    thumb_path = result.get("thumbnail_path")
    media_type = result.get("media_type", "video")
    title = result.get("title", "")
    author = result.get("author", "")

    caption = f"{emoji} <b>{platform.title()}</b>"
    if title:
        caption += f"\n📝 {title[:200]}"
    if author:
        caption += f"\n👤 @{author}"
    caption += "\n\n⚡️ @hofiz_bot"

    sent_msg = None
    try:
        if media_type == "video" and file_path and os.path.exists(file_path):
            video_file = FSInputFile(file_path)
            thumb_file = FSInputFile(thumb_path) if thumb_path and os.path.exists(thumb_path) else None
            sent_msg = await message.answer_video(
                video_file,
                caption=caption,
                parse_mode="HTML",
                thumbnail=thumb_file,
                reply_markup=download_result_kb(has_audio=bool(audio_path)),
            )
        elif media_type == "photo" and file_path and os.path.exists(file_path):
            photo_file = FSInputFile(file_path)
            sent_msg = await message.answer_photo(
                photo_file,
                caption=caption,
                parse_mode="HTML",
            )
        elif file_path and os.path.exists(file_path):
            doc_file = FSInputFile(file_path)
            sent_msg = await message.answer_document(
                doc_file,
                caption=caption,
                parse_mode="HTML",
            )

        # 5. file_id ni cache'lash
        if sent_msg:
            file_id = _extract_file_id(sent_msg, media_type)
            if file_id:
                await RedisService.cache_file_id(url, f"{file_id}|{media_type}")

        # 6. DB ga yozish
        if db_user:
            from src.db.engine import async_session
            from src.db.repositories.repos import DownloadRepo
            async with async_session() as session:
                repo = DownloadRepo(session)
                await repo.create(
                    user_id=db_user.id,
                    platform=platform,
                    url=url,
                    media_type=media_type,
                    file_id=_extract_file_id(sent_msg, media_type) if sent_msg else None,
                    title=title,
                )

        await RedisService.incr_stat("downloads")
        await RedisService.incr_stat(f"dl_{platform}")

    except Exception as e:
        logger.exception("Send media error: %s", e)
        await message.answer("❌ Media yuborishda xatolik. Qayta urinib ko'ring.")

    finally:
        # Progress xabarini o'chirish
        try:
            await progress_msg.delete()
        except Exception:
            pass

        # Temp fayllarni tozalash
        cleanup(file_path, audio_path, thumb_path)


@router.callback_query(lambda c: c.data == "dl_audio")
async def handle_audio_download(callback: CallbackQuery, bot: Bot):
    """Audio yuklab olish tugmasi bosilganda."""
    await callback.answer("🎵 Audio tayyorlanmoqda...")
    # TODO: audio_path ni Redis'dan olish va yuborish
    await callback.message.answer("🎵 Audio yuklab olish hozircha ishlab chiqilmoqda.")


def _extract_file_id(message: Message, media_type: str) -> str | None:
    """Yuborilgan xabardan file_id ajratish."""
    if media_type == "video" and message.video:
        return message.video.file_id
    elif media_type == "photo" and message.photo:
        return message.photo[-1].file_id
    elif media_type == "audio" and message.audio:
        return message.audio.file_id
    elif message.document:
        return message.document.file_id
    return None
