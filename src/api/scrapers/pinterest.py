"""Pinterest scraper — rasm va video + audio yuklab olish."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import uuid

import aiohttp

from src.api.scrapers.base import BaseScraper, MediaResult
from src.api.processors.ffmpeg import extract_audio, get_thumbnail
from src.common.exceptions import ScraperError

logger = logging.getLogger("hofiz.scraper.pinterest")


class PinterestScraper(BaseScraper):
    PLATFORM = "pinterest"

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def _resolve_short_url(self, url: str) -> str:
        """pin.it qisqa URL'ni to'liq URL'ga aylantirish."""
        if "pin.it" in url:
            session = await self._get_session()
            async with session.get(url, allow_redirects=False) as resp:
                return str(resp.headers.get("Location", url))
        return url

    async def get_info(self, url: str) -> dict:
        url = await self._resolve_short_url(url)
        session = await self._get_session()

        async with session.get(url) as resp:
            html = await resp.text()

        title_match = re.search(r'property="og:title"\s+content="([^"]*)"', html)
        desc_match = re.search(r'property="og:description"\s+content="([^"]*)"', html)

        return {
            "title": title_match.group(1) if title_match else "Pinterest",
            "description": desc_match.group(1) if desc_match else "",
        }

    async def download(self, url: str) -> MediaResult:
        url = await self._resolve_short_url(url)
        session = await self._get_session()

        async with session.get(url) as resp:
            if resp.status != 200:
                raise ScraperError("Pinterest sahifa yuklanmadi")
            html = await resp.text()

        # Video bor-yo'qligini tekshirish
        video_match = re.search(
            r'"contentUrl"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"', html
        )
        if not video_match:
            video_match = re.search(
                r'property="og:video"\s+content="(https?://[^"]+)"', html
            )

        if video_match:
            return await self._download_video(video_match.group(1), url, html, session)

        # Rasm yuklab olish
        return await self._download_image(url, html, session)

    async def _download_video(
        self, video_url: str, original_url: str, html: str,
        session: aiohttp.ClientSession
    ) -> MediaResult:
        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        async with session.get(video_url) as resp:
            if resp.status != 200:
                raise ScraperError("Pinterest video yuklanmadi")
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        title_match = re.search(r'property="og:title"\s+content="([^"]*)"', html)
        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)

        return MediaResult(
            platform=self.PLATFORM, url=original_url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title=title_match.group(1) if title_match else "Pinterest video",
            file_size=os.path.getsize(out_path),
        )

    async def _download_image(
        self, original_url: str, html: str,
        session: aiohttp.ClientSession
    ) -> MediaResult:
        # Eng yuqori sifatli rasm URL'ni topish
        image_match = re.search(
            r'property="og:image"\s+content="(https?://[^"]+)"', html
        )
        if not image_match:
            image_match = re.search(r'"url"\s*:\s*"(https://i\.pinimg\.com/originals/[^"]+)"', html)

        if not image_match:
            raise ScraperError("Pinterest rasm URL topilmadi")

        image_url = image_match.group(1)
        # Original sifatga almashtirish
        image_url = re.sub(r"/\d+x/", "/originals/", image_url)

        ext = "jpg"
        if ".png" in image_url:
            ext = "png"
        elif ".gif" in image_url:
            ext = "gif"

        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.{ext}")
        async with session.get(image_url) as resp:
            if resp.status != 200:
                raise ScraperError("Pinterest rasm yuklanmadi")
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        title_match = re.search(r'property="og:title"\s+content="([^"]*)"', html)
        return MediaResult(
            platform=self.PLATFORM, url=original_url, media_type="photo",
            file_path=out_path,
            title=title_match.group(1) if title_match else "Pinterest image",
            file_size=os.path.getsize(out_path),
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
