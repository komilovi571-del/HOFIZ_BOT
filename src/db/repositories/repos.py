from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Sequence

from sqlalchemy import select, func, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    User, Channel, Download, Recognition, Broadcast,
    StatsDaily, AdminUser, ChannelRequest, Subscription,
    Platform, BroadcastStatus, RequestStatus, ChannelType,
)


# ── Users ──────────────────────────────────────────────

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_or_create(
        self, telegram_id: int, username: str | None = None,
        full_name: str = "",
    ) -> tuple[User, bool]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.s.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            if username and user.username != username:
                user.username = username
            if full_name and user.full_name != full_name:
                user.full_name = full_name
            await self.s.commit()
            return user, False
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        )
        self.s.add(user)
        await self.s.commit()
        await self.s.refresh(user)
        return user, True

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.s.execute(stmt)
        return result.scalar_one_or_none()

    async def set_banned(self, telegram_id: int, banned: bool) -> None:
        await self.s.execute(
            update(User).where(User.telegram_id == telegram_id).values(is_banned=banned)
        )
        await self.s.commit()

    async def set_premium(self, telegram_id: int, premium: bool) -> None:
        await self.s.execute(
            update(User).where(User.telegram_id == telegram_id).values(is_premium=premium)
        )
        await self.s.commit()

    async def count_total(self) -> int:
        result = await self.s.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def count_active(self) -> int:
        result = await self.s.execute(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )
        return result.scalar_one()

    async def count_today(self) -> int:
        today = date.today()
        result = await self.s.execute(
            select(func.count(User.id)).where(func.date(User.created_at) == today)
        )
        return result.scalar_one()

    async def get_all_active_ids(self) -> Sequence[int]:
        result = await self.s.execute(
            select(User.telegram_id).where(
                User.is_active.is_(True), User.is_banned.is_(False)
            )
        )
        return result.scalars().all()

    async def search(self, query: str) -> Sequence[User]:
        stmt = select(User).where(
            (User.username.ilike(f"%{query}%"))
            | (User.full_name.ilike(f"%{query}%"))
            | (User.telegram_id == int(query) if query.isdigit() else False)
        ).limit(20)
        result = await self.s.execute(stmt)
        return result.scalars().all()


# ── Channels ───────────────────────────────────────────

class ChannelRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def add(
        self, channel_id: int, title: str,
        username: str | None = None,
        invite_link: str | None = None,
        channel_type: ChannelType = ChannelType.PUBLIC,
    ) -> Channel:
        ch = Channel(
            channel_id=channel_id, title=title,
            username=username, invite_link=invite_link,
            channel_type=channel_type,
        )
        self.s.add(ch)
        await self.s.commit()
        await self.s.refresh(ch)
        return ch

    async def get_active(self) -> Sequence[Channel]:
        result = await self.s.execute(
            select(Channel).where(Channel.is_active.is_(True))
        )
        return result.scalars().all()

    async def get_by_channel_id(self, channel_id: int) -> Channel | None:
        result = await self.s.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def toggle_active(self, channel_id: int) -> bool:
        ch = await self.get_by_channel_id(channel_id)
        if not ch:
            return False
        ch.is_active = not ch.is_active
        await self.s.commit()
        return ch.is_active

    async def remove(self, channel_id: int) -> None:
        await self.s.execute(
            delete(Channel).where(Channel.channel_id == channel_id)
        )
        await self.s.commit()

    async def update_type(self, channel_id: int, channel_type: ChannelType) -> None:
        await self.s.execute(
            update(Channel)
            .where(Channel.channel_id == channel_id)
            .values(channel_type=channel_type)
        )
        await self.s.commit()

    async def get_all(self) -> Sequence[Channel]:
        """Barcha kanallar — faol va nofaol."""
        result = await self.s.execute(select(Channel).order_by(Channel.is_active.desc()))
        return result.scalars().all()


# ── Downloads ──────────────────────────────────────────

class DownloadRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(
        self, user_id: int, platform: Platform, url: str,
        media_type, file_id: str | None = None,
        file_size: int | None = None, title: str | None = None,
    ) -> Download:
        dl = Download(
            user_id=user_id, platform=platform, url=url,
            media_type=media_type, file_id=file_id,
            file_size=file_size, title=title,
        )
        self.s.add(dl)
        await self.s.commit()
        return dl

    async def count_today(self) -> int:
        today = date.today()
        result = await self.s.execute(
            select(func.count(Download.id)).where(
                func.date(Download.created_at) == today
            )
        )
        return result.scalar_one()

    async def count_by_platform(self) -> dict[str, int]:
        result = await self.s.execute(
            select(Download.platform, func.count(Download.id))
            .group_by(Download.platform)
        )
        return {str(row[0].value): row[1] for row in result.all()}

    async def get_user_recent(
        self, user_id: int, limit: int = 10
    ) -> Sequence[Download]:
        result = await self.s.execute(
            select(Download)
            .where(Download.user_id == user_id)
            .order_by(Download.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# ── Recognitions ───────────────────────────────────────

class RecognitionRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, user_id: int, source_type, **kwargs) -> Recognition:
        rec = Recognition(user_id=user_id, source_type=source_type, **kwargs)
        self.s.add(rec)
        await self.s.commit()
        return rec

    async def count_today(self) -> int:
        today = date.today()
        result = await self.s.execute(
            select(func.count(Recognition.id)).where(
                func.date(Recognition.created_at) == today
            )
        )
        return result.scalar_one()

    async def get_user_recent(
        self, user_id: int, limit: int = 10
    ) -> Sequence[Recognition]:
        result = await self.s.execute(
            select(Recognition)
            .where(Recognition.user_id == user_id)
            .order_by(Recognition.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# ── Broadcasts ─────────────────────────────────────────

class BroadcastRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, admin_id: int, content: dict, total_users: int) -> Broadcast:
        bc = Broadcast(
            admin_id=admin_id, content=content, total_users=total_users
        )
        self.s.add(bc)
        await self.s.commit()
        await self.s.refresh(bc)
        return bc

    async def update_progress(
        self, broadcast_id: int, delivered: int, failed: int,
        status: BroadcastStatus | None = None,
    ) -> None:
        values: dict = {"delivered": delivered, "failed": failed}
        if status:
            values["status"] = status
        await self.s.execute(
            update(Broadcast).where(Broadcast.id == broadcast_id).values(**values)
        )
        await self.s.commit()


# ── Stats ──────────────────────────────────────────────

class StatsRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def upsert_today(self, **kwargs) -> None:
        today = date.today()
        stmt = pg_insert(StatsDaily).values(date=today, **kwargs)
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_=kwargs,
        )
        await self.s.execute(stmt)
        await self.s.commit()

    async def get_range(
        self, start: date, end: date
    ) -> Sequence[StatsDaily]:
        result = await self.s.execute(
            select(StatsDaily)
            .where(StatsDaily.date.between(start, end))
            .order_by(StatsDaily.date)
        )
        return result.scalars().all()


# ── Admin Users ────────────────────────────────────────

class AdminRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def is_admin(self, telegram_id: int) -> bool:
        result = await self.s.execute(
            select(AdminUser).where(AdminUser.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none() is not None

    async def get_role(self, telegram_id: int) -> str | None:
        result = await self.s.execute(
            select(AdminUser.role).where(AdminUser.telegram_id == telegram_id)
        )
        role = result.scalar_one_or_none()
        return role.value if role else None


# ── Channel Requests ───────────────────────────────────

class ChannelRequestRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, user_id: int, channel_id: int) -> ChannelRequest:
        req = ChannelRequest(user_id=user_id, channel_id=channel_id)
        self.s.add(req)
        await self.s.commit()
        return req

    async def get_pending(self, channel_id: int) -> Sequence[ChannelRequest]:
        result = await self.s.execute(
            select(ChannelRequest).where(
                ChannelRequest.channel_id == channel_id,
                ChannelRequest.status == RequestStatus.PENDING,
            )
        )
        return result.scalars().all()

    async def approve(self, request_id: int) -> None:
        await self.s.execute(
            update(ChannelRequest)
            .where(ChannelRequest.id == request_id)
            .values(status=RequestStatus.APPROVED, reviewed_at=func.now())
        )
        await self.s.commit()

    async def reject(self, request_id: int) -> None:
        await self.s.execute(
            update(ChannelRequest)
            .where(ChannelRequest.id == request_id)
            .values(status=RequestStatus.REJECTED, reviewed_at=func.now())
        )
        await self.s.commit()
