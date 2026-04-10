"""Media download service — bot'dan FastAPI ga so'rov yuborish."""

from __future__ import annotations

import logging

import aiohttp

from src.common.config import settings
from src.common.exceptions import DownloadError

logger = logging.getLogger("hofiz.service.download")


class DownloadService:
    """FastAPI media download API bilan bog'lanish."""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-Api-Key": settings.api_secret_key},
                timeout=aiohttp.ClientTimeout(total=120),
            )
        return self._session

    async def download(self, url: str, platform: str) -> dict:
        """Media yuklab olish so'rovi."""
        session = await self._get_session()
        api_url = f"{settings.api_base_url}/api/v1/download"

        async with session.post(api_url, json={"url": url, "platform": platform}) as resp:
            if resp.status == 422:
                data = await resp.json()
                raise DownloadError(data.get("detail", "Yuklab olish muvaffaqiyatsiz"))
            if resp.status != 200:
                raise DownloadError(f"API xatolik: {resp.status}")
            return await resp.json()

    async def get_info(self, url: str, platform: str) -> dict:
        """Media haqida ma'lumot olish."""
        session = await self._get_session()
        api_url = f"{settings.api_base_url}/api/v1/info"

        async with session.post(api_url, json={"url": url, "platform": platform}) as resp:
            if resp.status != 200:
                return {}
            return await resp.json()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# Global instance
download_service = DownloadService()
