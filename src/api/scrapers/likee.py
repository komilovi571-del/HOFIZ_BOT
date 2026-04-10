"""Likee scraper — suv belgisiz video + audio yuklab olish."""

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

logger = logging.getLogger("hofiz.scraper.likee")


class LikeeScraper(BaseScraper):
    PLATFORM = "likee"

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
        return {"title": "Likee video", "author": "", "platform": "likee"}

    async def download(self, url: str) -> MediaResult:
        # 1-usul: Likee API
        try:
            return await self._download_via_api(url)
        except Exception as e:
            logger.warning("Likee API failed: %s", e)

        # 2-usul: yt-dlp
        try:
            return await self._download_via_ytdlp(url)
        except Exception as e:
            logger.warning("yt-dlp Likee failed: %s", e)

        # 3-usul: Web scraping
        try:
            return await self._download_via_web(url)
        except Exception as e:
            logger.warning("Likee web scraping failed: %s", e)

        raise ScraperError("Likee'dan yuklab olish muvaffaqiyatsiz")

    async def _download_via_api(self, url: str) -> MediaResult:
        """Likee API orqali suv belgisiz video yuklab olish."""
        session = await self._get_session()

        # Post ID ni URL dan ajratish
        async with session.get(url, allow_redirects=True) as resp:
            final_url = str(resp.url)
            html = await resp.text()

        # Video URL'ni HTML dan topish (og:video yoki videoObject)
        video_match = re.search(r'property="og:video"\s+content="(https?://[^"]+)"', html)
        if not video_match:
            video_match = re.search(r'"playUrl"\s*:\s*"(https?://[^"]+)"', html)

        if not video_match:
            raise ScraperError("Likee video URL topilmadi")

        video_url = video_match.group(1).replace("\\u002F", "/")

        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        async with session.get(video_url) as resp:
            if resp.status != 200:
                raise ScraperError("Likee video yuklanmadi")
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        # Author va title
        title_match = re.search(r'property="og:title"\s+content="([^"]*)"', html)
        title = title_match.group(1) if title_match else "Likee video"

        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)

        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title=title,
            file_size=os.path.getsize(out_path),
        )

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
            raise ScraperError(f"yt-dlp Likee xatolik: {stderr.decode()[:200]}")

        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)

        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title="Likee video",
            file_size=os.path.getsize(out_path),
        )

    async def _download_via_web(self, url: str) -> MediaResult:
        """Web sahifadan to'g'ridan-to'g'ri yuklab olish."""
        session = await self._get_session()
        async with session.get(url) as resp:
            html = await resp.text()

        video_match = re.search(r'"videoUrl"\s*:\s*"(https?://[^"]+)"', html)
        if not video_match:
            raise ScraperError("Likee web: video URL topilmadi")

        video_url = video_match.group(1).replace("\\u002F", "/")

        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        async with session.get(video_url) as resp:
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        audio_path = await extract_audio(out_path)
        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            title="Likee video",
            file_size=os.path.getsize(out_path),
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
