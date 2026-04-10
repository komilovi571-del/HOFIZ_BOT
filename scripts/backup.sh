#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════
# HOFIZ BOT — Backup skripti (cron uchun)
# Har kuni 03:00 da ishga tushirish:
#   0 3 * * * /path/to/scripts/backup.sh >> /var/log/hofiz_backup.log 2>&1
# ═══════════════════════════════════════════════════════════

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backup boshlandi..."

# PostgreSQL dump
docker compose exec -T postgres pg_dump \
    -U "${DB_USER:-hofiz}" \
    -d "${DB_NAME:-hofiz_db}" \
    --format=custom \
    --compress=9 \
    > "${BACKUP_DIR}/hofiz_${TIMESTAMP}.dump"

echo "[$(date)] Dump yaratildi: hofiz_${TIMESTAMP}.dump"

# Eski backuplarni o'chirish
find "$BACKUP_DIR" -name "hofiz_*.dump" -mtime +"$RETENTION_DAYS" -delete
echo "[$(date)] $RETENTION_DAYS kundan eski backuplar o'chirildi"

echo "[$(date)] ✅ Backup tugadi"
