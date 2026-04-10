"""Instagram scraper — post, reel, IGTV yuklab olish."""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid

import aiohttp

from src.api.scrapers.base import BaseScraper, MediaResult
from src.api.processors.ffmpeg import extract_audio, get_thumbnail
from src.common.exceptions import ScraperError

logger = logging.getLogger("hofiz.scraper.instagram")

# Instagram GraphQL API (login-siz public postlar)
GRAPHQL_URL = "https://www.instagram.com/graphql/query/"
MEDIA_URL_RE = re.compile(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_\-]+)")


class InstagramScraper(BaseScraper):
    PLATFORM = "instagram"

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
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "X-IG-App-ID": "936619743392459",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    def _extract_shortcode(self, url: str) -> str:
        match = MEDIA_URL_RE.search(url)
        if not match:
            raise ScraperError(f"Instagram URL noto'g'ri: {url}")
        return match.group(1)

    async def get_info(self, url: str) -> dict:
        shortcode = self._extract_shortcode(url)
        session = await self._get_session()

        # Instagram oEmbed API (public, login-siz)
        oembed_url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/p/{shortcode}/"
        try:
            async with session.get(oembed_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "shortcode": shortcode,
                        "title": data.get("title", ""),
                        "author": data.get("author_name", ""),
                        "thumbnail": data.get("thumbnail_url", ""),
                    }
        except Exception as e:
            logger.warning("Instagram oEmbed failed: %s", e)

        return {"shortcode": shortcode, "title": "", "author": ""}

    async def download(self, url: str) -> MediaResult:
        shortcode = self._extract_shortcode(url)
        session = await self._get_session()

        # 1-usul: Instagram media API (public)
        api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
        try:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return await self._process_api_response(data, url)
        except Exception as e:
            logger.warning("Instagram API 1 failed: %s", e)

        # 2-usul: GraphQL query
        try:
            return await self._download_via_graphql(shortcode, url, session)
        except Exception as e:
            logger.warning("Instagram GraphQL failed: %s", e)

        # 3-usul: yt-dlp fallback
        return await self._download_via_ytdlp(url)

    async def _process_api_response(self, data: dict, url: str) -> MediaResult:
        session = await self._get_session()
        item = data.get("graphql", {}).get("shortcode_media", data.get("items", [{}])[0] if "items" in data else {})

        is_video = item.get("is_video", False)
        video_url = item.get("video_url", "")
        display_url = item.get("display_url", "")

        if is_video and video_url:
            file_path = await self._download_file(session, video_url, "mp4")
            audio_path = await extract_audio(file_path) if file_path else None
            thumb_path = await self._download_file(session, display_url, "jpg") if display_url else None
            return MediaResult(
                platform=self.PLATFORM, url=url, media_type="video",
                file_path=file_path, audio_path=audio_path,
                thumbnail_path=thumb_path,
                title=item.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")[:200] if item.get("edge_media_to_caption") else "",
                author=item.get("owner", {}).get("username", ""),
            )
        elif display_url:
            file_path = await self._download_file(session, display_url, "jpg")
            return MediaResult(
                platform=self.PLATFORM, url=url, media_type="photo",
                file_path=file_path,
                title="Instagram post",
                author=item.get("owner", {}).get("username", ""),
            )

        raise ScraperError("Instagram media topilmadi")

    async def _download_via_graphql(self, shortcode: str, url: str, session: aiohttp.ClientSession) -> MediaResult:
        params = {
            "query_hash": "b3055c01b4b222b8a47dc12b090e4e64",
            "variables": f'{{"shortcode":"{shortcode}"}}',
        }
        async with session.get(GRAPHQL_URL, params=params) as resp:
            if resp.status != 200:
                raise ScraperError("GraphQL so'rov muvaffaqiyatsiz")
            data = await resp.json()

        media = data.get("data", {}).get("shortcode_media", {})
        if not media:
            raise ScraperError("GraphQL natija bo'sh")

        return await self._process_api_response({"graphql": {"shortcode_media": media}}, url)

    async def _download_via_ytdlp(self, url: str) -> MediaResult:
        """yt-dlp orqali yuklab olish (fallback)."""
        import asyncio

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
            raise ScraperError(f"yt-dlp Instagram xatolik: {stderr.decode()[:200]}")

        audio_path = await extract_audio(out_path)
        thumb_path = await get_thumbnail(out_path)
        return MediaResult(
            platform=self.PLATFORM, url=url, media_type="video",
            file_path=out_path, audio_path=audio_path, thumbnail_path=thumb_path,
        )

    async def _download_file(self, session: aiohttp.ClientSession, url: str, ext: str) -> str | None:
        out_path = os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.{ext}")
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                with open(out_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        f.write(chunk)
            return out_path
        except Exception as e:
            logger.error("Download file failed: %s", e)
            return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
