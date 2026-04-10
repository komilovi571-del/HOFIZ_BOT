"""Custom filters — admin va platform URL aniqlash."""

from __future__ import annotations

import re
from aiogram.filters import Filter
from aiogram.types import Message

from src.common.config import settings

# Platforma emoji'lari (inline mode va boshqa handlerlarda ham ishlatiladi)
PLATFORM_EMOJI: dict[str, str] = {
    "instagram": "📸",
    "tiktok": "🎵",
    "snapchat": "👻",
    "likee": "❤️",
    "pinterest": "📌",
}

# Platforma URL regex pattern'lari
PLATFORM_PATTERNS: dict[str, re.Pattern] = {
    "instagram": re.compile(
        r"(?:https?://)?(?:www\.)?(?:instagram\.com|instagr\.am)/(?:p|reel|tv|stories)/[\w\-]+",
        re.IGNORECASE,
    ),
    "tiktok": re.compile(
        r"(?:https?://)?(?:www\.|vm\.|vt\.)?tiktok\.com/[\w\-@/]+",
        re.IGNORECASE,
    ),
    "snapchat": re.compile(
        r"(?:https?://)?(?:www\.)?(?:snapchat\.com|story\.snapchat\.com)/[\w\-@/]+",
        re.IGNORECASE,
    ),
    "likee": re.compile(
        r"(?:https?://)?(?:www\.|l\.)?likee\.video/[\w\-@/]+",
        re.IGNORECASE,
    ),
    "pinterest": re.compile(
        r"(?:https?://)?(?:www\.|pin\.it/|[\w]+\.)?pinterest\.[\w]+/[\w\-/]+",
        re.IGNORECASE,
    ),
}


def detect_platform(url: str) -> str | None:
    """URL dan platforma nomini aniqlash."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in settings.admin_ids


class IsSupportedURL(Filter):
    async def __call__(self, message: Message) -> bool | dict:
        if not message.text:
            return False
        for platform, pattern in PLATFORM_PATTERNS.items():
            match = pattern.search(message.text)
            if match:
                return {"platform": platform, "url": match.group(0)}
        return False
