"""Base scraper — barcha scraperlar uchun abstrakt klass."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MediaResult:
    """Yuklab olingan media natijasi."""
    platform: str
    url: str
    media_type: str  # video | photo | audio | story | reel
    file_path: str | None = None
    audio_path: str | None = None
    thumbnail_path: str | None = None
    title: str | None = None
    author: str | None = None
    duration: float = 0
    file_size: int = 0
    photos: list[str] = field(default_factory=list)  # Pinterest/IG carousel uchun


class BaseScraper(abc.ABC):
    """Barcha platform scraperlar uchun asos."""

    PLATFORM: str = ""

    @abc.abstractmethod
    async def download(self, url: str) -> MediaResult:
        """URL dan media yuklab olish."""

    @abc.abstractmethod
    async def get_info(self, url: str) -> dict:
        """URL haqida ma'lumot olish (yuklamasdan)."""

    async def close(self) -> None:
        """Resurslarni tozalash."""
