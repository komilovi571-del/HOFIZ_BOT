"""Snapchat scraper — spotlight/stories yuklab olish."""

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

logger = logging.getLogger("hofiz.scraper.snapchat")

SNAP_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:snapchat\.com|story\.snapchat\.com)/[\w\-@/]+",
    re.IGNORECASE,
)


class SnapchatScraper(BaseScraper):
    PLATFORM = "snapchat"

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

    async def get_info(self, url: str) -> dict:
        return {"title": "Snapchat video", "author": "", "platform": "snapchat"}

    async def download(self, url: str) -> MediaResult:
        # 1-usul: yt-dlp (Snapchat spotlight/stories uchun)
        try:
            return await self._download_via_ytdlp(url)
        except Exception as e:
            logger.warning("yt-dlp Snapchat failed: %s", e)

        # 2-usul: web scraping (HTML dan video URL ajratish)
        try:
            return await self._download_via_web(url)
        except Exception as e:
            logger.warning("Snapchat web scraping failed: %s", e)

        raise ScraperError("Snapchat'dan yuklab olish muvaffaqiyatsiz")

    async def _download_via_ytdlp(self, url: str) -> MediaResult:
        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--no-warnings",
            "-o", out_path,
            "--no-playlist",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not os.path.exists(out_path):
            raise ScraperError(f"yt-dlp Snapchat xatolik: {stderr.decode()[:200]}")

        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)

        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title="Snapchat video",
            file_size=os.path.getsize(out_path),
        )

    async def _download_via_web(self, url: str) -> MediaResult:
        """Snapchat web sahifadan video URL ajratish."""
        session = await self._get_session()

        async with session.get(url) as resp:
            if resp.status != 200:
                raise ScraperError("Snapchat sahifa yuklanmadi")
            html = await resp.text()

        # Video URL ni HTML dan topish
        video_match = re.search(r'"contentUrl"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"', html)
        if not video_match:
            video_match = re.search(r'source\s+src="(https?://[^"]+\.mp4[^"]*)"', html)

        if not video_match:
            raise ScraperError("Snapchat video URL topilmadi")

        video_url = video_match.group(1)

        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        async with session.get(video_url) as resp:
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)

        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title="Snapchat video",
            file_size=os.path.getsize(out_path),
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
