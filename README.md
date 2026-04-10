# 🤖 HOFIZ BOT

**Telegram media download va musiqa aniqlash boti** — 100K+ foydalanuvchilar uchun yuqori samaradorlikda ishlaydi.

## ✨ Imkoniyatlar

- 📥 **Media yuklash** — Instagram, TikTok, Snapchat, Likee, Pinterest (watermark-siz)
- 🎵 **Musiqa aniqlash** — Ovozli xabar, audio, video, video note orqali (Shazam o'rniga)
- 🔍 **Inline rejim** — Istalgan chatda URL jo'natib yuklab olish
- 👑 **Admin panel** — Statistika, broadcast, foydalanuvchi boshqaruvi, kanal boshqaruvi
- 📢 **Obuna tizimi** — Public, private va request-based kanallar
- 💾 **Backup tizimi** — Avtomatik zaxira nusxa va tiklash
- ⚡ **Yuqori tezlik** — Redis cache, file_id kesh, asinxron arxitektura

## 🏗️ Arxitektura

```
┌─────────────┐     ┌─────────────┐     ┌──────────┐
│  Telegram    │────▶│  Bot        │────▶│  Redis   │
│  Users       │◀────│  (aiogram)  │────▶│  Cache   │
└─────────────┘     └──────┬──────┘     └──────────┘
                           │
                    ┌──────▼──────┐     ┌──────────┐
                    │  FastAPI    │────▶│ PostgreSQL│
                    │  (scrapers) │     │  Database │
                    └─────────────┘     └──────────┘
```

## 🚀 Ishga tushirish

### 1. `.env` sozlash

```bash
cp .env.example .env
nano .env  # Tokenlarni kiriting
```

### 2. Docker Compose bilan ishga tushirish

```bash
docker compose up -d
```

### 3. Migratsiya

```bash
docker compose exec bot alembic upgrade head
```

### 4. Loglarni ko'rish

```bash
docker compose logs -f bot
```

## 📂 Loyiha tuzilishi

```
HOFIZ_BOT/
├── src/
│   ├── common/          # Umumiy config, exceptions
│   ├── db/              # Database models, engine, repositories
│   ├── bot/             # Telegram bot
│   │   ├── handlers/    # Buyruq handlerlar
│   │   ├── keyboards/   # Inline klaviaturalar
│   │   ├── middlewares/  # Rate limit, obuna tekshiruv
│   │   ├── filters/     # Admin, URL, platform filterlar
│   │   ├── states/      # FSM holatlar
│   │   └── services/    # Redis, music, download, backup
│   └── api/             # FastAPI media download xizmati
│       ├── scrapers/    # Platform scraperlari
│       └── processors/  # FFmpeg media qayta ishlash
├── alembic/             # Database migratsiyalar
├── nginx/               # Nginx reverse proxy
├── scripts/             # Deploy va backup skriptlar
├── requirements/        # Python kutubxonalar
├── docker-compose.yml   # Barcha xizmatlar
└── .env.example         # Muhit o'zgaruvchilari
```

## ⚙️ Texnologiyalar

| Texnologiya | Vazifasi |
|---|---|
| Python 3.12 | Asosiy til |
| aiogram 3.x | Telegram bot framework |
| FastAPI | Media download API |
| PostgreSQL 16 | Asosiy database |
| Redis 7 | Cache va rate limiting |
| FFmpeg | Media qayta ishlash |
| yt-dlp | Video yuklab olish |
| Docker Compose | Konteynerlashtirish |

## 🔧 Admin buyruqlar

- `/admin` — Admin panelga kirish
- Statistika ko'rish (kunlik/oylik/jami)
- Broadcast jo'natish (barcha/premium/faol foydalanuvchilar)
- Foydalanuvchi qidirish/ban/premium
- Kanal qo'shish/o'chirish/turi o'zgartirish
- Backup yaratish/tiklash

## 📦 Deploy (Yandex Cloud)

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

## 📄 Litsenziya

MIT
