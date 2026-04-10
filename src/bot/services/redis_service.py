"""Redis cache service — tez kesh va rate-limiting uchun."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from src.common.config import settings


class RedisService:
    _pool: aioredis.Redis | None = None

    @classmethod
    async def connect(cls) -> None:
        cls._pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )

    @classmethod
    async def close(cls) -> None:
        if cls._pool:
            await cls._pool.close()

    @classmethod
    def pool(cls) -> aioredis.Redis:
        assert cls._pool is not None, "Redis not connected"
        return cls._pool

    # ── Generic ────────────────────────────────────────

    @classmethod
    async def get(cls, key: str) -> str | None:
        return await cls.pool().get(key)

    @classmethod
    async def set(cls, key: str, value: str, ttl: int = 3600) -> None:
        await cls.pool().set(key, value, ex=ttl)

    @classmethod
    async def delete(cls, key: str) -> None:
        await cls.pool().delete(key)

    @classmethod
    async def get_json(cls, key: str) -> Any | None:
        data = await cls.get(key)
        return json.loads(data) if data else None

    @classmethod
    async def set_json(cls, key: str, value: Any, ttl: int = 3600) -> None:
        await cls.set(key, json.dumps(value, default=str), ttl)

    # ── Rate Limiting ──────────────────────────────────

    @classmethod
    async def check_rate_limit(
        cls, user_id: int, max_requests: int = 10, window: int = 60
    ) -> bool:
        """True agar limit oshgan bo'lsa."""
        key = f"rate:{user_id}"
        current = await cls.pool().incr(key)
        if current == 1:
            await cls.pool().expire(key, window)
        return current > max_requests

    @classmethod
    async def get_rate_ttl(cls, user_id: int) -> int:
        return await cls.pool().ttl(f"rate:{user_id}")

    # ── Download Cache (file_id) ───────────────────────

    @classmethod
    def url_hash(cls, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    @classmethod
    async def get_cached_file_id(cls, url: str) -> str | None:
        return await cls.get(f"dl:{cls.url_hash(url)}")

    @classmethod
    async def cache_file_id(cls, url: str, file_id: str, ttl: int = 172800) -> None:
        await cls.set(f"dl:{cls.url_hash(url)}", file_id, ttl)

    # ── Subscription Cache ─────────────────────────────

    @classmethod
    async def get_sub_status(cls, user_id: int) -> bool | None:
        result = await cls.get(f"sub:{user_id}")
        if result is None:
            return None
        return result == "1"

    @classmethod
    async def set_sub_status(cls, user_id: int, subscribed: bool, ttl: int = 1800) -> None:
        await cls.set(f"sub:{user_id}", "1" if subscribed else "0", ttl)

    @classmethod
    async def invalidate_sub(cls, user_id: int) -> None:
        await cls.delete(f"sub:{user_id}")

    # ── Inline Cache ───────────────────────────────────

    @classmethod
    async def get_inline_cache(cls, query: str) -> list | None:
        return await cls.get_json(f"inline:{cls.url_hash(query)}")

    @classmethod
    async def set_inline_cache(cls, query: str, results: list, ttl: int = 21600) -> None:
        await cls.set_json(f"inline:{cls.url_hash(query)}", results, ttl)

    # ── Stats Counters ─────────────────────────────────

    @classmethod
    async def incr_stat(cls, field: str, amount: int = 1) -> None:
        await cls.pool().hincrby("stats:today", field, amount)

    @classmethod
    async def get_today_stats(cls) -> dict:
        data = await cls.pool().hgetall("stats:today")
        return {k: int(v) for k, v in data.items()} if data else {}

    @classmethod
    async def reset_today_stats(cls) -> None:
        await cls.pool().delete("stats:today")
