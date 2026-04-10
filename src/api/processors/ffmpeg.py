"""FFmpeg async wrapper — audio ajratish, video kompressiya, format konvertatsiya."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid

logger = logging.getLogger("hofiz.ffmpeg")


async def _run_ffmpeg(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode or 0, stderr.decode(errors="replace")


def _tmp(ext: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"hofiz_{uuid.uuid4().hex}.{ext}")


async def extract_audio(input_path: str, output_format: str = "mp3") -> str | None:
    """Video/audio fayldan audio ajratib olish."""
    out = _tmp(output_format)
    code, err = await _run_ffmpeg(
        "-i", input_path,
        "-vn",
        "-c:a", "libmp3lame" if output_format == "mp3" else "aac",
        "-q:a", "2",
        "-y", out,
    )
    if code != 0:
        logger.error("extract_audio failed: %s", err)
        return None
    return out


async def convert_ogg_to_mp3(input_path: str) -> str | None:
    """OGG (voice message) dan MP3 ga konvertatsiya."""
    out = _tmp("mp3")
    code, err = await _run_ffmpeg(
        "-i", input_path,
        "-c:a", "libmp3lame",
        "-q:a", "2",
        "-y", out,
    )
    if code != 0:
        logger.error("ogg_to_mp3 failed: %s", err)
        return None
    return out


async def compress_video(input_path: str, max_size_mb: int = 50) -> str | None:
    """Videoni Telegram limitiga moslashtirish (kompressiya)."""
    out = _tmp("mp4")

    # Avval original hajmni tekshirish
    file_size = os.path.getsize(input_path)
    if file_size <= max_size_mb * 1024 * 1024:
        return input_path  # Kompressiya kerak emas

    code, err = await _run_ffmpeg(
        "-i", input_path,
        "-c:v", "libx264",
        "-crf", "28",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y", out,
    )
    if code != 0:
        logger.error("compress_video failed: %s", err)
        return None
    return out


async def get_duration(input_path: str) -> float:
    """Media davomiyligini olish (soniyalarda)."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except (ValueError, AttributeError):
        return 0.0


async def get_thumbnail(input_path: str) -> str | None:
    """Videodan birinchi kadr (thumbnail) olish."""
    out = _tmp("jpg")
    code, err = await _run_ffmpeg(
        "-i", input_path,
        "-vf", "thumbnail",
        "-frames:v", "1",
        "-y", out,
    )
    if code != 0:
        logger.error("get_thumbnail failed: %s", err)
        return None
    return out


def cleanup(*paths: str | None) -> None:
    """Vaqtinchalik fayllarni o'chirish."""
    for p in paths:
        if p and os.path.exists(p) and "hofiz_" in os.path.basename(p):
            try:
                os.unlink(p)
            except OSError:
                pass
