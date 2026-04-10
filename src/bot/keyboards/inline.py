"""Keyboard builders for the bot — inline & reply markups."""

from __future__ import annotations
from typing import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.models import Channel, ChannelType


# ── Asosiy menyu ───────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Shazam — Musiqa aniqlash")],
            [
                KeyboardButton(text="📥 Yuklab olish"),
                KeyboardButton(text="📊 Statistika"),
            ],
            [
                KeyboardButton(text="ℹ️ Yordam"),
                KeyboardButton(text="⚙️ Sozlamalar"),
            ],
        ],
        resize_keyboard=True,
    )


# ── Obuna tekshirish ──────────────────────────────────

def subscription_kb(channels: Sequence[Channel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        if ch.channel_type == ChannelType.REQUEST:
            builder.row(
                InlineKeyboardButton(
                    text=f"📨 {ch.title} (so'rov yuborish)",
                    callback_data=f"req_channel:{ch.channel_id}",
                )
            )
        elif ch.invite_link:
            builder.row(
                InlineKeyboardButton(text=f"➕ {ch.title}", url=ch.invite_link)
            )
        elif ch.username:
            builder.row(
                InlineKeyboardButton(
                    text=f"➕ {ch.title}", url=f"https://t.me/{ch.username}"
                )
            )
    builder.row(
        InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")
    )
    return builder.as_markup()


# ── Admin menyu ────────────────────────────────────────

def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
        InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin:broadcast"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users"),
        InlineKeyboardButton(text="📺 Kanallar", callback_data="admin:channels"),
    )
    builder.row(
        InlineKeyboardButton(text="💾 Zaxira nusxa", callback_data="admin:backup"),
        InlineKeyboardButton(text="🔙 Yopish", callback_data="admin:close"),
    )
    return builder.as_markup()


# ── Admin — Kanal boshqaruvi ────────────────────────────

def channel_manage_kb(channels: Sequence[Channel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        status = "🟢" if ch.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {ch.title} [{ch.channel_type.value}]",
                callback_data=f"ch_toggle:{ch.channel_id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch_add"),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:menu"),
    )
    return builder.as_markup()


def channel_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌐 Oddiy (public)", callback_data="ch_type:public"),
        InlineKeyboardButton(text="🔒 Maxfiy (private)", callback_data="ch_type:private"),
    )
    builder.row(
        InlineKeyboardButton(text="📨 So'rovli (request)", callback_data="ch_type:request"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin:channels"),
    )
    return builder.as_markup()


# ── Broadcast ──────────────────────────────────────────

def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yuborish", callback_data="bc_confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel"),
    )
    return builder.as_markup()


def broadcast_target_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Barchaga", callback_data="bc_target:all"),
        InlineKeyboardButton(text="⭐ Faollarga", callback_data="bc_target:active"),
    )
    builder.row(
        InlineKeyboardButton(text="💎 Premiumlarga", callback_data="bc_target:premium"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin:menu"),
    )
    return builder.as_markup()


# ── Musiqa natijalari ──────────────────────────────────

def music_result_kb(
    lyrics_url: str | None = None,
    spotify_url: str | None = None,
    apple_url: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if spotify_url:
        builder.row(
            InlineKeyboardButton(text="🎧 Spotify", url=spotify_url),
        )
    if apple_url:
        builder.row(
            InlineKeyboardButton(text="🍎 Apple Music", url=apple_url),
        )
    if lyrics_url:
        builder.row(
            InlineKeyboardButton(text="📝 Qo'shiq matni", callback_data="show_lyrics"),
        )
    return builder.as_markup()


# ── Yuklab olish natijalari ────────────────────────────

def download_result_kb(has_audio: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_audio:
        builder.row(
            InlineKeyboardButton(text="🎵 Audio yuklab olish", callback_data="dl_audio"),
        )
    return builder.as_markup()


# ── Cancel / Orqaga ───────────────────────────────────

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ]
    )


def back_kb(callback: str = "admin:menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback)]
        ]
    )


# ── User boshqaruvi ──────────────────────────────────

def user_manage_kb(telegram_id: int, is_banned: bool, is_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    ban_text = "🔓 Banni olib tashlash" if is_banned else "🚫 Banlash"
    prem_text = "⭐ Premiumni olib tashlash" if is_premium else "💎 Premium berish"
    builder.row(
        InlineKeyboardButton(text=ban_text, callback_data=f"usr_ban:{telegram_id}"),
    )
    builder.row(
        InlineKeyboardButton(text=prem_text, callback_data=f"usr_prem:{telegram_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:users"),
    )
    return builder.as_markup()
