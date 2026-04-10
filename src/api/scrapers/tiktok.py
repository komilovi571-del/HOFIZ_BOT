"""TikTok scraper — suv belgisiz video + audio yuklab olish."""

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

logger = logging.getLogger("hofiz.scraper.tiktok")

TIKTOK_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|vm\.|vt\.)?tiktok\.com/(?:@[\w.]+/video/(\d+)|(\w+))",
    re.IGNORECASE,
)


class TikTokScraper(BaseScraper):
    PLATFORM = "tiktok"

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
        """Qisqa URL'ni to'liq URL'ga aylantirish."""
        if "vm.tiktok.com" in url or "vt.tiktok.com" in url:
            session = await self._get_session()
            async with session.get(url, allow_redirects=False) as resp:
                return str(resp.headers.get("Location", url))
        return url

    async def get_info(self, url: str) -> dict:
        url = await self._resolve_short_url(url)
        session = await self._get_session()

        # oEmbed API
        oembed_url = f"https://www.tiktok.com/oembed?url={url}"
        try:
            async with session.get(oembed_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "title": data.get("title", ""),
                        "author": data.get("author_name", ""),
                        "thumbnail": data.get("thumbnail_url", ""),
                    }
        except Exception as e:
            logger.warning("TikTok oEmbed failed: %s", e)

        return {"title": "TikTok video", "author": ""}

    async def download(self, url: str) -> MediaResult:
        url = await self._resolve_short_url(url)

        # 1-usul: yt-dlp (eng ishonchli, suv belgisiz)
        try:
            return await self._download_via_ytdlp(url)
        except Exception as e:
            logger.warning("yt-dlp TikTok failed: %s", e)

        # 2-usul: TikTok API (tikwm.com — tez, suv belgisiz)
        try:
            return await self._download_via_api(url)
        except Exception as e:
            logger.warning("TikTok API failed: %s", e)

        raise ScraperError("TikTok'dan yuklab olish muvaffaqiyatsiz")

    async def _download_via_ytdlp(self, url: str) -> MediaResult:
        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--no-warnings",
            "--no-watermark",
            "-o", out_path,
            "--no-playlist",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not os.path.exists(out_path):
            raise ScraperError(f"yt-dlp TikTok xatolik: {stderr.decode()[:200]}")

        info = await self.get_info(url)
        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)

        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title=info.get("title", ""),
            author=info.get("author", ""),
            file_size=os.path.getsize(out_path),
        )

    async def _download_via_api(self, url: str) -> MediaResult:
        """tikwm.com ochiq API orqali suv belgisiz yuklab olish."""
        session = await self._get_session()
        api_url = "https://www.tikwm.com/api/"
        data = {"url": url, "hd": 1}

        async with session.post(api_url, data=data) as resp:
            if resp.status != 200:
                raise ScraperError("TikWM API javob bermadi")
            result = await resp.json()

        if result.get("code") != 0:
            raise ScraperError("TikWM natija bo'sh")

        video_data = result.get("data", {})
        play_url = video_data.get("hdplay") or video_data.get("play", "")
        if not play_url:
            raise ScraperError("TikTok video URL topilmadi")

        # Video yuklab olish
        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.mp4")
        async with session.get(play_url) as resp:
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        audio_path = await extract_audio(out_path)
        thumb_path = None
        cover = video_data.get("cover", "")
        if cover:
            thumb_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.jpg")
            async with session.get(cover) as resp:
                with open(thumb_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        f.write(chunk)

        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path,
            thumbnail_path=thumb_path,
            title=video_data.get("title", ""),
            author=video_data.get("author", {}).get("unique_id", ""),
            duration=video_data.get("duration", 0),
            file_size=os.path.getsize(out_path),
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
