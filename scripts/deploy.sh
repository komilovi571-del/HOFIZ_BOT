#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════
# HOFIZ BOT — Yandex Cloud deploy skripti
# ═══════════════════════════════════════════════════════════

echo "⚡ HOFIZ BOT — Deploy boshlanyapti..."

# 1. Tizimni yangilash
echo "📦 Paketlarni yangilash..."
sudo apt-get update -y && sudo apt-get upgrade -y

# 2. Docker o'rnatish
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker o'rnatilmoqda..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
fi

# 3. Docker Compose o'rnatish
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Docker Compose o'rnatilmoqda..."
    sudo apt-get install -y docker-compose-plugin
fi

# 4. UFW sozlash
echo "🔒 Firewall sozlanmoqda..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# 5. .env tekshirish
if [ ! -f .env ]; then
    echo "⚠️  .env fayli topilmadi! .env.example dan nusxa oling:"
    echo "    cp .env.example .env"
    echo "    nano .env"
    exit 1
fi

# 6. Build va ishga tushirish
echo "🔨 Docker image'larni build qilish..."
docker compose build --no-cache

echo "🚀 Xizmatlarni ishga tushirish..."
docker compose up -d

# 7. Migratsiya
echo "📊 Database migratsiya..."
docker compose exec bot alembic upgrade head

echo ""
echo "✅ HOFIZ BOT muvaffaqiyatli deploy qilindi!"
echo ""
echo "📋 Foydali buyruqlar:"
echo "  docker compose logs -f bot     — Bot loglarini ko'rish"
echo "  docker compose logs -f api     — API loglarini ko'rish"
echo "  docker compose ps              — Xizmatlar holati"
echo "  docker compose restart bot     — Botni qayta ishga tushirish"
echo "  docker compose down            — Hammasini to'xtatish"
