"""FastAPI media download service — ichki API xizmati."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel

from src.api.scrapers.instagram import InstagramScraper
from src.api.scrapers.tiktok import TikTokScraper
from src.api.scrapers.snapchat import SnapchatScraper
from src.api.scrapers.likee import LikeeScraper
from src.api.scrapers.pinterest import PinterestScraper
from src.api.scrapers.base import MediaResult
from src.api.processors.ffmpeg import compress_video
from src.common.config import settings
from src.common.exceptions import ScraperError, PlatformNotSupportedError

logger = logging.getLogger("hofiz.api")

# Scraperlar ro'yxati
SCRAPERS = {
    "instagram": InstagramScraper,
    "tiktok": TikTokScraper,
    "snapchat": SnapchatScraper,
    "likee": LikeeScraper,
    "pinterest": PinterestScraper,
}

# Parallel yuklab olishni cheklash (server yuklanishini boshqarish)
download_semaphore = asyncio.Semaphore(20)

# Scraper instance'lari (reuse qilish uchun)
_scraper_instances: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("📡 Media Download API ishga tushmoqda...")
    yield
    # Barcha scraper sessiyalarni yopish
    for scraper in _scraper_instances.values():
        await scraper.close()
    logger.info("Media Download API to'xtadi.")


app = FastAPI(
    title="HOFIZ Media Download API",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Auth ───────────────────────────────────────────────

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Noto'g'ri API kalit")
    return True


# ── Schemas ────────────────────────────────────────────

class DownloadRequest(BaseModel):
    url: str
    platform: str


class DownloadResponse(BaseModel):
    platform: str
    media_type: str
    file_path: str | None = None
    audio_path: str | None = None
    thumbnail_path: str | None = None
    title: str | None = None
    author: str | None = None
    duration: float = 0
    file_size: int = 0
    photos: list[str] = []


class InfoResponse(BaseModel):
    title: str = ""
    author: str = ""
    thumbnail: str = ""
    platform: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    scrapers: list[str] = []


# ── Helpers ────────────────────────────────────────────

def _get_scraper(platform: str):
    if platform not in SCRAPERS:
        raise PlatformNotSupportedError(f"Platforma qo'llab-quvvatlanmaydi: {platform}")
    if platform not in _scraper_instances:
        _scraper_instances[platform] = SCRAPERS[platform]()
    return _scraper_instances[platform]


# ── Endpoints ──────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        scrapers=list(SCRAPERS.keys()),
    )


@app.post("/api/v1/download", response_model=DownloadResponse, dependencies=[Depends(verify_api_key)])
async def download_media(req: DownloadRequest):
    """Media yuklab olish — platform va URL bo'yicha."""
    scraper = _get_scraper(req.platform)

    async with download_semaphore:
        try:
            result: MediaResult = await scraper.download(req.url)
        except ScraperError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.exception("Download error: %s", e)
            raise HTTPException(status_code=500, detail="Yuklab olishda xatolik yuz berdi")

    # Video kompressiya (Telegram 50MB limit)
    if result.file_path and result.media_type == "video":
        compressed = await compress_video(result.file_path)
        if compressed and compressed != result.file_path:
            result.file_path = compressed

    return DownloadResponse(
        platform=result.platform,
        media_type=result.media_type,
        file_path=result.file_path,
        audio_path=result.audio_path,
        thumbnail_path=result.thumbnail_path,
        title=result.title,
        author=result.author,
        duration=result.duration,
        file_size=result.file_size,
        photos=result.photos,
    )


@app.post("/api/v1/info", response_model=InfoResponse, dependencies=[Depends(verify_api_key)])
async def get_info(req: DownloadRequest):
    """Media haqida ma'lumot — yuklamasdan."""
    scraper = _get_scraper(req.platform)
    try:
        info = await scraper.get_info(req.url)
    except Exception as e:
        logger.warning("Info error: %s", e)
        info = {}

    return InfoResponse(
        title=info.get("title", ""),
        author=info.get("author", ""),
        thumbnail=info.get("thumbnail", ""),
        platform=req.platform,
    )
