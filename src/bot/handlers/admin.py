"""Admin panel handleri — statistika, broadcast, foydalanuvchi va kanal boshqaruvi."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot.filters.filters import IsAdmin
from src.bot.keyboards.inline import (
    admin_menu_kb, channel_manage_kb, channel_type_kb,
    broadcast_target_kb, broadcast_confirm_kb,
    user_manage_kb, back_kb,
)
from src.bot.states.states import BroadcastStates, ChannelAddStates, UserSearchStates
from src.bot.services.redis_service import RedisService
from src.db.engine import async_session
from src.db.models import ChannelType, BroadcastStatus
from src.db.repositories.repos import (
    UserRepo, ChannelRepo, DownloadRepo, RecognitionRepo,
    BroadcastRepo,
)

logger = logging.getLogger("hofiz.handler.admin")
router = Router(name="admin")


# ── Admin menyu ────────────────────────────────────────

@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: Message):
    await message.answer(
        "🔐 <b>Admin Panel</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔐 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "admin:close")
async def admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


# ── Statistika ─────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    await callback.answer()

    redis_stats = await RedisService.get_today_stats()

    async with async_session() as session:
        user_repo = UserRepo(session)
        dl_repo = DownloadRepo(session)
        rec_repo = RecognitionRepo(session)

        total_users = await user_repo.count_total()
        active_users = await user_repo.count_active()
        today_users = await user_repo.count_today()
        today_downloads = await dl_repo.count_today()
        today_recognitions = await rec_repo.count_today()
        platform_stats = await dl_repo.count_by_platform()

    platform_text = ""
    if platform_stats:
        for p, count in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True):
            platform_text += f"  • {p.title()}: {count}\n"

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"  • Jami: {total_users:,}\n"
        f"  • Faol: {active_users:,}\n"
        f"  • Bugun yangi: {today_users}\n\n"
        f"📥 <b>Bugungi faollik:</b>\n"
        f"  • Yuklab olishlar: {today_downloads}\n"
        f"  • Musiqa aniqlash: {today_recognitions}\n"
        f"  • Inline tanlash: {redis_stats.get('inline_chosen', 0)}\n\n"
    )

    if platform_text:
        text += f"🏆 <b>Top platformalar (jami):</b>\n{platform_text}\n"

    text += (
        f"💾 <b>Redis statistika (bugun):</b>\n"
        f"  • Yuklab olishlar: {redis_stats.get('downloads', 0)}\n"
        f"  • Aniqlashlar: {redis_stats.get('recognitions', 0)}\n"
        f"  • Yangi foydalanuvchilar: {redis_stats.get('new_users', 0)}\n"
    )

    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")


# ── Broadcast ──────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📢 <b>Xabar yuborish</b>\n\n"
        "Kimga yuborishni tanlang:",
        reply_markup=broadcast_target_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("bc_target:"))
async def broadcast_target(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":")[1]
    await state.update_data(target=target)
    await state.set_state(BroadcastStates.waiting_content)
    await callback.message.edit_text(
        f"📢 Maqsad: <b>{'Barchaga' if target == 'all' else 'Faollarga' if target == 'active' else 'Premiumlarga'}</b>\n\n"
        "Endi xabar matnini yuboring (matn, rasm, video, audio — ixtiyoriy):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_content)
async def broadcast_content(message: Message, state: FSMContext):
    # Xabar kontentini saqlash
    content = {
        "text": message.text or message.caption or "",
        "photo": message.photo[-1].file_id if message.photo else None,
        "video": message.video.file_id if message.video else None,
        "audio": message.audio.file_id if message.audio else None,
        "document": message.document.file_id if message.document else None,
    }
    await state.update_data(content=content)
    await state.set_state(BroadcastStates.confirm)

    data = await state.get_data()
    target = data.get("target", "all")

    await message.answer(
        f"📢 <b>Xabar tasdiqlash</b>\n\n"
        f"Maqsad: <b>{'Barchaga' if target == 'all' else 'Faollarga' if target == 'active' else 'Premiumlarga'}</b>\n"
        f"Matn: {(content.get('text') or 'yo'q')[:100]}\n"
        f"Rasm: {'✅' if content.get('photo') else '❌'}\n"
        f"Video: {'✅' if content.get('video') else '❌'}\n\n"
        f"Yuborishni tasdiqlaysizmi?",
        reply_markup=broadcast_confirm_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "bc_confirm", BroadcastStates.confirm)
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    await callback.answer("📢 Yuborish boshlandi!")

    content = data.get("content", {})
    target = data.get("target", "all")

    async with async_session() as session:
        user_repo = UserRepo(session)
        user_ids = await user_repo.get_all_active_ids()

        bc_repo = BroadcastRepo(session)
        broadcast = await bc_repo.create(
            admin_id=callback.from_user.id,
            content=content,
            total_users=len(user_ids),
        )

    progress = await callback.message.edit_text(
        f"📢 <b>Yuborish jarayonida...</b>\n"
        f"📊 0/{len(user_ids)} | ✅ 0 | ❌ 0",
        parse_mode="HTML",
    )

    delivered = 0
    failed = 0

    for i, uid in enumerate(user_ids):
        try:
            if content.get("photo"):
                await bot.send_photo(uid, content["photo"], caption=content.get("text", ""), parse_mode="HTML")
            elif content.get("video"):
                await bot.send_video(uid, content["video"], caption=content.get("text", ""), parse_mode="HTML")
            elif content.get("audio"):
                await bot.send_audio(uid, content["audio"], caption=content.get("text", ""), parse_mode="HTML")
            elif content.get("text"):
                await bot.send_message(uid, content["text"], parse_mode="HTML")
            delivered += 1
        except Exception:
            failed += 1

        # Progress yangilash (har 50 ta xabardan keyin)
        if (i + 1) % 50 == 0:
            try:
                await progress.edit_text(
                    f"📢 <b>Yuborish jarayonida...</b>\n"
                    f"📊 {i + 1}/{len(user_ids)} | ✅ {delivered} | ❌ {failed}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        # Telegram rate limit (30 msg/sec)
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

    # Yakuniy natija
    async with async_session() as session:
        bc_repo = BroadcastRepo(session)
        await bc_repo.update_progress(
            broadcast.id, delivered, failed, BroadcastStatus.COMPLETED
        )

    try:
        await progress.edit_text(
            f"✅ <b>Yuborish tugadi!</b>\n\n"
            f"📊 Jami: {len(user_ids)}\n"
            f"✅ Muvaffaqiyatli: {delivered}\n"
            f"❌ Muvaffaqiyatsiz: {failed}",
            reply_markup=back_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(lambda c: c.data == "bc_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ Bekor qilindi")
    await callback.message.edit_text(
        "🔐 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


# ── Foydalanuvchi boshqaruvi ──────────────────────────

@router.callback_query(lambda c: c.data == "admin:users")
async def admin_users(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserSearchStates.waiting_query)
    await callback.message.edit_text(
        "👥 <b>Foydalanuvchi boshqaruvi</b>\n\n"
        "Foydalanuvchi ID, username yoki ismini yuboring:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(UserSearchStates.waiting_query)
async def search_user(message: Message, state: FSMContext):
    query = message.text.strip()
    await state.clear()

    async with async_session() as session:
        repo = UserRepo(session)

        # Avval ID bo'yicha izlash
        if query.isdigit():
            user = await repo.get_by_telegram_id(int(query))
            if user:
                await _show_user_info(message, user)
                return

        # Ism/username bo'yicha izlash
        users = await repo.search(query)
        if not users:
            await message.answer(
                "😔 Foydalanuvchi topilmadi.",
                reply_markup=back_kb(),
            )
            return

        if len(users) == 1:
            await _show_user_info(message, users[0])
            return

        text = f"👥 <b>{len(users)} ta natija:</b>\n\n"
        for u in users[:10]:
            status = "🚫" if u.is_banned else "💎" if u.is_premium else "👤"
            text += f"{status} <code>{u.telegram_id}</code> — {u.full_name} (@{u.username or 'yo`q'})\n"

        text += "\nAniqroq ID yuboring."
        await message.answer(text, reply_markup=back_kb(), parse_mode="HTML")


async def _show_user_info(message: Message, user):
    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"📛 Ism: {user.full_name}\n"
        f"👤 Username: @{user.username or 'yo`q'}\n"
        f"🌐 Til: {user.language}\n"
        f"💎 Premium: {'✅' if user.is_premium else '❌'}\n"
        f"🚫 Ban: {'✅' if user.is_banned else '❌'}\n"
        f"📅 Ro'yxatdan: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )
    await message.answer(
        text,
        reply_markup=user_manage_kb(user.telegram_id, user.is_banned, user.is_premium),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("usr_ban:"))
async def toggle_ban(callback: CallbackQuery):
    telegram_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        repo = UserRepo(session)
        user = await repo.get_by_telegram_id(telegram_id)
        if not user:
            await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
            return

        new_status = not user.is_banned
        await repo.set_banned(telegram_id, new_status)

    action = "🚫 Banlandi" if new_status else "🔓 Ban olib tashlandi"
    await callback.answer(f"{action}!", show_alert=True)

    await callback.message.edit_reply_markup(
        reply_markup=user_manage_kb(telegram_id, new_status, user.is_premium)
    )


@router.callback_query(lambda c: c.data and c.data.startswith("usr_prem:"))
async def toggle_premium(callback: CallbackQuery):
    telegram_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        repo = UserRepo(session)
        user = await repo.get_by_telegram_id(telegram_id)
        if not user:
            await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
            return

        new_status = not user.is_premium
        await repo.set_premium(telegram_id, new_status)

    action = "💎 Premium berildi" if new_status else "⭐ Premium olib tashlandi"
    await callback.answer(f"{action}!", show_alert=True)

    await callback.message.edit_reply_markup(
        reply_markup=user_manage_kb(telegram_id, user.is_banned, new_status)
    )


# ── Kanal boshqaruvi ──────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:channels")
async def admin_channels(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        repo = ChannelRepo(session)
        all_channels = await repo.get_all()

    await callback.message.edit_text(
        f"📺 <b>Kanallar boshqaruvi</b>\n\n"
        f"Jami: {len(all_channels)} ta kanal\n"
        f"🟢 Faol | 🔴 Nofaol",
        reply_markup=channel_manage_kb(all_channels),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ch_toggle:"))
async def toggle_channel(callback: CallbackQuery):
    channel_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        repo = ChannelRepo(session)
        new_status = await repo.toggle_active(channel_id)

    status_text = "🟢 Faollashtirildi" if new_status else "🔴 O'chirildi"
    await callback.answer(f"{status_text}!", show_alert=True)

    # Kanalar ro'yxatini yangilash
    async with async_session() as session:
        repo = ChannelRepo(session)
        channels = await repo.get_active()

    await callback.message.edit_reply_markup(reply_markup=channel_manage_kb(channels))


@router.callback_query(lambda c: c.data == "ch_add")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChannelAddStates.waiting_channel)
    await callback.message.edit_text(
        "📺 <b>Kanal qo'shish</b>\n\n"
        "Kanalni forward qiling yoki kanal ID/username yuboring:\n"
        "Masalan: <code>@channel_username</code> yoki <code>-1001234567890</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ChannelAddStates.waiting_channel)
async def add_channel_receive(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip() if message.text else ""

    # Forward message dan kanal aniqlash
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
        title = message.forward_from_chat.title or "Noma'lum"
        username = message.forward_from_chat.username
    elif text.startswith("@"):
        # Username bo'yicha
        try:
            chat = await bot.get_chat(text)
            channel_id = chat.id
            title = chat.title or text
            username = chat.username
        except Exception:
            await message.answer("❌ Kanal topilmadi. Botni kanalga admin qiling.")
            return
    elif text.lstrip("-").isdigit():
        # ID bo'yicha
        try:
            chat = await bot.get_chat(int(text))
            channel_id = chat.id
            title = chat.title or text
            username = chat.username
        except Exception:
            await message.answer("❌ Kanal topilmadi. Botni kanalga admin qiling.")
            return
    else:
        await message.answer("❌ Noto'g'ri format. @username yoki ID yuboring.")
        return

    await state.update_data(channel_id=channel_id, title=title, username=username)
    await state.set_state(ChannelAddStates.waiting_type)

    await message.answer(
        f"📺 Kanal: <b>{title}</b>\n"
        f"ID: <code>{channel_id}</code>\n\n"
        f"Kanal turini tanlang:",
        reply_markup=channel_type_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("ch_type:"), ChannelAddStates.waiting_type)
async def add_channel_type(callback: CallbackQuery, state: FSMContext, bot: Bot):
    type_str = callback.data.split(":")[1]
    channel_type = ChannelType(type_str)

    data = await state.get_data()
    await state.clear()

    channel_id = data["channel_id"]
    title = data["title"]
    username = data.get("username")

    # Invite link olish (private kanallar uchun)
    invite_link = None
    if channel_type in (ChannelType.PRIVATE, ChannelType.REQUEST):
        try:
            link_obj = await bot.create_chat_invite_link(channel_id)
            invite_link = link_obj.invite_link
        except Exception:
            invite_link = None

    async with async_session() as session:
        repo = ChannelRepo(session)
        # Mavjud bo'lsa yangilamaslik
        existing = await repo.get_by_channel_id(channel_id)
        if existing:
            await callback.answer("⚠️ Kanal allaqachon mavjud!", show_alert=True)
            return

        await repo.add(
            channel_id=channel_id,
            title=title,
            username=username,
            invite_link=invite_link,
            channel_type=channel_type,
        )

    type_names = {
        ChannelType.PUBLIC: "🌐 Oddiy (public)",
        ChannelType.PRIVATE: "🔒 Maxfiy (private)",
        ChannelType.REQUEST: "📨 So'rovli (request)",
    }

    await callback.answer("✅ Kanal qo'shildi!", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📺 {title}\n"
        f"📋 Tur: {type_names.get(channel_type, type_str)}\n"
        f"{'🔗 Link: ' + invite_link if invite_link else ''}",
        reply_markup=back_kb("admin:channels"),
        parse_mode="HTML",
    )


# ── Backup boshqaruvi ─────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:backup")
async def admin_backup(callback: CallbackQuery):
    await callback.answer()

    from src.bot.services.backup_service import backup_service

    text = (
        "💾 <b>Zaxira nusxa boshqaruvi</b>\n\n"
        f"📅 Avtomatik backup: {'✅ Yoqilgan' if True else '❌ O'chirilgan'}\n"
        f"⏰ Vaqt: Har kuni soat 02:00\n"
        f"📊 Saqlash: 30 kun\n"
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Hozir backup olish", callback_data="backup:now")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:menu")],
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "backup:now")
async def backup_now(callback: CallbackQuery):
    await callback.answer("💾 Backup boshlanmoqda...", show_alert=True)

    from src.bot.services.backup_service import backup_service
    try:
        path = await backup_service.create_backup()
        await callback.message.edit_text(
            f"✅ <b>Backup muvaffaqiyatli!</b>\n\n"
            f"📁 Fayl: <code>{path}</code>",
            reply_markup=back_kb("admin:backup"),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Backup muvaffaqiyatsiz:\n<code>{e}</code>",
            reply_markup=back_kb("admin:backup"),
            parse_mode="HTML",
        )
