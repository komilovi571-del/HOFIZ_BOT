"""Musiqa aniqlash xizmati — AudD + Genius API integratsiyasi."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

from src.common.config import settings
from src.common.exceptions import RecognitionError

logger = logging.getLogger("hofiz.service.music")


@dataclass
class MusicResult:
    """Musiqa aniqlash natijasi."""
    found: bool = False
    title: str = ""
    artist: str = ""
    album: str = ""
    release_date: str = ""
    confidence: float = 0.0
    spotify_url: str = ""
    apple_music_url: str = ""
    lyrics_url: str = ""
    lyrics_text: str = ""
    thumbnail: str = ""


class MusicService:
    """AudD va Genius API orqali musiqa aniqlash."""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def recognize_from_file(self, file_path: str) -> MusicResult:
        """Audio fayldan musiqa aniqlash (AudD API)."""
        session = await self._get_session()

        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("file", f, filename="audio.mp3")
            data.add_field("api_token", settings.audd_api_key)
            data.add_field("return", "apple_music,spotify,lyrics")

            async with session.post("https://api.audd.io/", data=data) as resp:
                if resp.status != 200:
                    raise RecognitionError("AudD API javob bermadi")
                result = await resp.json()

        return self._parse_audd_response(result)

    async def recognize_from_url(self, audio_url: str) -> MusicResult:
        """Audio URL dan musiqa aniqlash."""
        session = await self._get_session()

        params = {
            "api_token": settings.audd_api_key,
            "url": audio_url,
            "return": "apple_music,spotify,lyrics",
        }

        async with session.post("https://api.audd.io/", data=params) as resp:
            if resp.status != 200:
                raise RecognitionError("AudD API javob bermadi")
            result = await resp.json()

        return self._parse_audd_response(result)

    def _parse_audd_response(self, data: dict) -> MusicResult:
        """AudD javobini MusicResult ga aylantirish."""
        if data.get("status") != "success":
            error = data.get("error", {}).get("error_message", "Noma'lum xato")
            logger.warning("AudD error: %s", error)
            return MusicResult(found=False)

        result = data.get("result")
        if not result:
            return MusicResult(found=False)

        # Spotify URL
        spotify_url = ""
        spotify_data = result.get("spotify")
        if spotify_data and spotify_data.get("external_urls"):
            spotify_url = spotify_data["external_urls"].get("spotify", "")

        # Apple Music URL
        apple_url = ""
        apple_data = result.get("apple_music")
        if apple_data:
            apple_url = apple_data.get("url", "")

        # Lyrics
        lyrics_text = ""
        lyrics_data = result.get("lyrics")
        if lyrics_data:
            lyrics_text = lyrics_data.get("lyrics", "")

        # Thumbnail (Spotify album art)
        thumbnail = ""
        if spotify_data and spotify_data.get("album", {}).get("images"):
            images = spotify_data["album"]["images"]
            thumbnail = images[0].get("url", "") if images else ""

        return MusicResult(
            found=True,
            title=result.get("title", ""),
            artist=result.get("artist", ""),
            album=result.get("album", ""),
            release_date=result.get("release_date", ""),
            confidence=float(result.get("score", 0) or 0),
            spotify_url=spotify_url,
            apple_music_url=apple_url,
            lyrics_url="",
            lyrics_text=lyrics_text,
            thumbnail=thumbnail,
        )

    async def get_lyrics(self, title: str, artist: str) -> str:
        """Genius API orqali qo'shiq matni olish."""
        if not settings.genius_api_key:
            return ""

        session = await self._get_session()
        headers = {"Authorization": f"Bearer {settings.genius_api_key}"}
        params = {"q": f"{title} {artist}"}

        try:
            async with session.get(
                "https://api.genius.com/search",
                headers=headers,
                params=params,
            ) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()

            hits = data.get("response", {}).get("hits", [])
            if not hits:
                return ""

            # Birinchi natijaning URL'ini qaytarish
            return hits[0].get("result", {}).get("url", "")
        except Exception as e:
            logger.warning("Genius API error: %s", e)
            return ""

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# Global instance
music_service = MusicService()
