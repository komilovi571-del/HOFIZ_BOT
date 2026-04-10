"""Musiqa aniqlash (Shazam) handleri — ovoz, audio, video xabarlarni qayta ishlash."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from aiogram import Router, Bot, F
from aiogram.types import Message, FSInputFile, CallbackQuery

from src.bot.services.music_service import music_service, MusicResult
from src.bot.services.redis_service import RedisService
from src.bot.keyboards.inline import music_result_kb
from src.api.processors.ffmpeg import convert_ogg_to_mp3, extract_audio, cleanup

logger = logging.getLogger("hofiz.handler.music")
router = Router(name="music_recognition")


@router.message(F.text == "🔍 Shazam — Musiqa aniqlash")
async def shazam_menu(message: Message):
    text = (
        "🎵 <b>Musiqa aniqlash (Shazam)</b>\n\n"
        "Quyidagilardan birini yuboring:\n"
        "  🎤 Ovozli xabar\n"
        "  🎵 Audio fayl\n"
        "  🎬 Video fayl\n"
        "  📹 Video xabar\n\n"
        "Men qo'shiq nomini, ijrochisini va matnini topaman! ⚡️"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot, db_user=None):
    """Ovozli xabar — musiqa aniqlash."""
    progress = await message.answer("🎵 Musiqa aniqlanmoqda...\n⏳ Iltimos, kuting...")

    file_path = None
    mp3_path = None
    try:
        # 1. Voice message yuklab olish
        file = await bot.get_file(message.voice.file_id)
        file_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.ogg")
        await bot.download_file(file.file_path, file_path)

        # 2. OGG → MP3 konvertatsiya
        mp3_path = await convert_ogg_to_mp3(file_path)
        if not mp3_path:
            await progress.edit_text("❌ Audio konvertatsiya muvaffaqiyatsiz.")
            return

        # 3. AudD'ga yuborish
        result = await music_service.recognize_from_file(mp3_path)
        await _send_music_result(message, progress, result, db_user, "voice")

    except Exception as e:
        logger.exception("Voice recognition error: %s", e)
        await progress.edit_text("❌ Musiqa aniqlashda xatolik yuz berdi.")
    finally:
        cleanup(file_path, mp3_path)


@router.message(F.audio)
async def handle_audio(message: Message, bot: Bot, db_user=None):
    """Audio fayl — musiqa aniqlash."""
    progress = await message.answer("🎵 Musiqa aniqlanmoqda...\n⏳ Iltimos, kuting...")

    file_path = None
    try:
        file = await bot.get_file(message.audio.file_id)
        ext = "mp3"
        if message.audio.mime_type:
            ext = message.audio.mime_type.split("/")[-1]
        file_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.{ext}")
        await bot.download_file(file.file_path, file_path)

        result = await music_service.recognize_from_file(file_path)
        await _send_music_result(message, progress, result, db_user, "audio")

    except Exception as e:
        logger.exception("Audio recognition error: %s", e)
        await progress.edit_text("❌ Musiqa aniqlashda xatolik yuz berdi.")
    finally:
        cleanup(file_path)


@router.message(F.video)
async def handle_video_recognition(message: Message, bot: Bot, db_user=None):
    """Video fayl — audiodan musiqa aniqlash."""
    # Bot filter — agar bu media download'dan kelgan video bo'lsa, o'tkazib yuboramiz
    if message.caption and "@hofiz_bot" in message.caption:
        return

    progress = await message.answer("🎵 Videodan musiqa aniqlanmoqda...\n⏳ Iltimos, kuting...")

    file_path = None
    audio_path = None
    try:
        file = await bot.get_file(message.video.file_id)
        file_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        await bot.download_file(file.file_path, file_path)

        # Audio ajratib olish
        audio_path = await extract_audio(file_path)
        if not audio_path:
            await progress.edit_text("❌ Videodan audio ajratib olib bo'lmadi.")
            return

        result = await music_service.recognize_from_file(audio_path)
        await _send_music_result(message, progress, result, db_user, "video")

    except Exception as e:
        logger.exception("Video recognition error: %s", e)
        await progress.edit_text("❌ Musiqa aniqlashda xatolik yuz berdi.")
    finally:
        cleanup(file_path, audio_path)


@router.message(F.video_note)
async def handle_video_note(message: Message, bot: Bot, db_user=None):
    """Video xabar (dumaloq) — musiqa aniqlash."""
    progress = await message.answer("🎵 Video xabardan musiqa aniqlanmoqda...\n⏳ Iltimos, kuting...")

    file_path = None
    audio_path = None
    try:
        file = await bot.get_file(message.video_note.file_id)
        file_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        await bot.download_file(file.file_path, file_path)

        audio_path = await extract_audio(file_path)
        if not audio_path:
            await progress.edit_text("❌ Video xabardan audio ajratib olib bo'lmadi.")
            return

        result = await music_service.recognize_from_file(audio_path)
        await _send_music_result(message, progress, result, db_user, "video_note")

    except Exception as e:
        logger.exception("Video note recognition error: %s", e)
        await progress.edit_text("❌ Musiqa aniqlashda xatolik yuz berdi.")
    finally:
        cleanup(file_path, audio_path)


async def _send_music_result(
    message: Message,
    progress: Message,
    result: MusicResult,
    db_user,
    source_type: str,
):
    """Musiqa aniqlash natijasini yuborish."""
    try:
        await progress.delete()
    except Exception:
        pass

    if not result.found:
        await message.answer(
            "😔 <b>Qo'shiq topilmadi</b>\n\n"
            "💡 Maslahat:\n"
            "  • Aniqroq audio yuboring\n"
            "  • Kamroq shovqin bo'lsin\n"
            "  • Kamida 5-10 soniya audio yuboring",
            parse_mode="HTML",
        )
        return

    text = (
        "🎵 <b>Qo'shiq topildi!</b>\n\n"
        f"🎶 <b>Nom:</b> {result.title}\n"
        f"🎤 <b>Ijrochi:</b> {result.artist}\n"
    )
    if result.album:
        text += f"💿 <b>Album:</b> {result.album}\n"
    if result.release_date:
        text += f"📅 <b>Chiqish:</b> {result.release_date}\n"

    text += "\n⚡️ @hofiz_bot"

    # Lyrics matnini Redis'ga saqlash (1 soat, foydalanuvchi ID bo'yicha)
    if result.lyrics_text:
        await RedisService.set(
            f"lyrics:{message.from_user.id}",
            result.lyrics_text[:4000],
            3600,
        )

    kb = music_result_kb(
        lyrics_url=result.lyrics_url or ("1" if result.lyrics_text else ""),
        spotify_url=result.spotify_url,
        apple_url=result.apple_music_url,
    )

    await message.answer(text, reply_markup=kb, parse_mode="HTML")

    # Statistika
    await RedisService.incr_stat("recognitions")

    # DB ga yozish
    if db_user:
        from src.db.engine import async_session
        from src.db.repositories.repos import RecognitionRepo
        async with async_session() as session:
            repo = RecognitionRepo(session)
            await repo.create(
                user_id=db_user.id,
                source_type=source_type,
                song_title=result.title,
                artist=result.artist,
                album=result.album,
                confidence=result.confidence,
                lyrics_url=result.lyrics_url,
            )


@router.callback_query(lambda c: c.data == "show_lyrics")
async def show_lyrics_callback(callback: CallbackQuery):
    """Qo'shiq matni tugmasi bosilganda."""
    await callback.answer("📝 Qo'shiq matni yuklanmoqda...")

    lyrics = await RedisService.get(f"lyrics:{callback.from_user.id}")
    if lyrics:
        # Telegram 4096 limit — agar uzun bo'lsa bo'lib yuborish
        header = "📝 <b>Qo'shiq matni</b>\n\n"
        if len(header) + len(lyrics) <= 4096:
            await callback.message.answer(header + lyrics, parse_mode="HTML")
        else:
            await callback.message.answer(header, parse_mode="HTML")
            # Uzun matni qismlarga bo'lib yuborish
            for i in range(0, len(lyrics), 4096):
                await callback.message.answer(lyrics[i:i + 4096])
    else:
        await callback.message.answer(
            "📝 <b>Qo'shiq matni</b>\n\n"
            "😔 Matn topilmadi. Genius.com saytidan qidiring.",
            parse_mode="HTML",
        )
