"""Start va asosiy buyruqlar handleri."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from src.bot.keyboards.inline import main_menu_kb

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user=None, is_new_user: bool = False):
    if is_new_user:
        text = (
            "🎉 <b>Xush kelibsiz, HOFIZ BOT'ga!</b>\n\n"
            "⚡️ Men sizga quyidagi imkoniyatlarni taqdim etaman:\n\n"
            "📥 <b>Media yuklab olish (suv belgisiz):</b>\n"
            "  • Instagram — post, Reels, IGTV + audio\n"
            "  • TikTok — video + audio\n"
            "  • Snapchat — video + audio\n"
            "  • Likee — video + audio\n"
            "  • Pinterest — video va rasmlar + audio\n\n"
            "🎵 <b>Shazam — Musiqa aniqlash:</b>\n"
            "  • Ovozli xabar yuboring\n"
            "  • Video/audio fayl yuboring\n"
            "  • Qo'shiq nomi va matnini topaman!\n\n"
            "💡 <b>Foydalanish:</b> Shunchaki link yuboring yoki audio/ovoz yuboring!\n"
            "🔍 Inline rejim: <code>@hofiz_bot link_yoki_qo'shiq</code>"
        )
    else:
        text = (
            "👋 <b>Qaytganingizdan xursandman!</b>\n\n"
            "📥 Link yuboring — yuklab beraman\n"
            "🎵 Audio/ovoz yuboring — qo'shiqni aniqlaman\n"
            "🔍 Inline: <code>@hofiz_bot</code>"
        )

    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "ℹ️ <b>HOFIZ BOT — Yordam</b>\n\n"
        "📥 <b>Media yuklab olish:</b>\n"
        "Quyidagi platformalar linkini yuboring:\n"
        "  • Instagram (post, Reels, IGTV)\n"
        "  • TikTok\n"
        "  • Snapchat\n"
        "  • Likee\n"
        "  • Pinterest\n\n"
        "🎵 <b>Musiqa aniqlash (Shazam):</b>\n"
        "  • 🎤 Ovozli xabar yuboring\n"
        "  • 🎵 Audio fayl yuboring\n"
        "  • 🎬 Video yuboring\n"
        "  • 📹 Video xabar yuboring\n\n"
        "🔍 <b>Inline rejim:</b>\n"
        "Istalgan chatda <code>@hofiz_bot link</code> yozing\n\n"
        "⚡️ Bot juda tez ishlaydi va suv belgisiz yuklab beradi!"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "ℹ️ Yordam")
async def btn_help(message: Message):
    await cmd_help(message)


@router.message(F.text == "📊 Statistika")
async def btn_my_stats(message: Message, db_user=None):
    if not db_user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    from src.db.engine import async_session
    from src.db.repositories.repos import DownloadRepo, RecognitionRepo

    async with async_session() as session:
        dl_repo = DownloadRepo(session)
        rec_repo = RecognitionRepo(session)
        recent_downloads = await dl_repo.get_user_recent(db_user.id, limit=5)
        recent_recs = await rec_repo.get_user_recent(db_user.id, limit=5)

    text = (
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"👤 ID: <code>{db_user.telegram_id}</code>\n"
        f"📅 Ro'yxatdan o'tgan: {db_user.created_at.strftime('%d.%m.%Y')}\n"
        f"💎 Premium: {'✅' if db_user.is_premium else '❌'}\n\n"
    )

    if recent_downloads:
        text += "📥 <b>So'nggi yuklab olishlar:</b>\n"
        for dl in recent_downloads:
            text += f"  • {dl.platform.value.title()} — {dl.created_at.strftime('%d.%m %H:%M')}\n"

    if recent_recs:
        text += "\n🎵 <b>So'nggi aniqlashlar:</b>\n"
        for rec in recent_recs:
            title = rec.song_title or "Noma'lum"
            artist = rec.artist or ""
            text += f"  • {title} — {artist} ({rec.created_at.strftime('%d.%m %H:%M')})\n"

    await message.answer(text, parse_mode="HTML")
