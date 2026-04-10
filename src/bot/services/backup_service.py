"""Backup xizmati — PostgreSQL va Redis zaxira nusxalash."""

from __future__ import annotations

import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime

from src.common.config import settings
from src.common.exceptions import BackupError

logger = logging.getLogger("hofiz.service.backup")

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "backups")


class BackupService:
    """PostgreSQL va Redis zaxira nusxa xizmati."""

    def __init__(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)

    async def create_backup(self) -> str:
        """PostgreSQL ni pg_dump bilan zaxiralash."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = os.path.join(BACKUP_DIR, f"hofiz_db_{timestamp}.sql")
        gz_file = f"{dump_file}.gz"

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.db_password

        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-h", settings.db_host,
            "-p", str(settings.db_port),
            "-U", settings.db_user,
            "-d", settings.db_name,
            "-F", "p",
            "-f", dump_file,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise BackupError(f"pg_dump muvaffaqiyatsiz: {stderr.decode()[:200]}")

        # Gzip bilan siqish
        with open(dump_file, "rb") as f_in:
            with gzip.open(gz_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Siqilmagan faylni o'chirish
        os.unlink(dump_file)

        logger.info("Backup yaratildi: %s", gz_file)

        # Eski backup'larni tozalash
        await self._cleanup_old_backups()

        return gz_file

    async def restore_backup(self, backup_path: str) -> None:
        """Backup'dan PostgreSQL ni tiklash."""
        if not os.path.exists(backup_path):
            raise BackupError(f"Backup fayl topilmadi: {backup_path}")

        # Gzip dan ochish
        sql_file = backup_path.replace(".gz", "")
        if backup_path.endswith(".gz"):
            with gzip.open(backup_path, "rb") as f_in:
                with open(sql_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.db_password

        proc = await asyncio.create_subprocess_exec(
            "psql",
            "-h", settings.db_host,
            "-p", str(settings.db_port),
            "-U", settings.db_user,
            "-d", settings.db_name,
            "-f", sql_file,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise BackupError(f"Restore muvaffaqiyatsiz: {stderr.decode()[:200]}")

        # Ochilgan faylni tozalash
        if sql_file != backup_path and os.path.exists(sql_file):
            os.unlink(sql_file)

        logger.info("Restore muvaffaqiyatli: %s", backup_path)

    async def _cleanup_old_backups(self) -> None:
        """Eski backup fayllarini o'chirish."""
        files = sorted(
            [
                os.path.join(BACKUP_DIR, f)
                for f in os.listdir(BACKUP_DIR)
                if f.startswith("hofiz_db_") and f.endswith(".gz")
            ],
            key=os.path.getmtime,
            reverse=True,
        )

        # Oxirgi N ta saqlash, qolganlarini o'chirish
        max_backups = settings.backup_retention_days
        for old_file in files[max_backups:]:
            try:
                os.unlink(old_file)
                logger.info("Eski backup o'chirildi: %s", old_file)
            except OSError:
                pass

    def list_backups(self) -> list[dict]:
        """Mavjud backup'lar ro'yxati."""
        files = []
        if not os.path.exists(BACKUP_DIR):
            return files

        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.startswith("hofiz_db_") and f.endswith(".gz"):
                path = os.path.join(BACKUP_DIR, f)
                size = os.path.getsize(path)
                files.append({
                    "name": f,
                    "path": path,
                    "size_mb": round(size / 1024 / 1024, 2),
                    "created": datetime.fromtimestamp(os.path.getmtime(path)),
                })
        return files


# Global instance
backup_service = BackupService()
