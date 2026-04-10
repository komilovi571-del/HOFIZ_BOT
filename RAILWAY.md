# 🚂 Railway Deploy Yo'riqnomasi — HOFIZ BOT

Railway — Docker va GitHub bilan ishlaydi, bepul tier mavjud ($5/oy kredit).

---

## Bosqichlar

### 1. GitHub repo tayyorlash

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/SIZNING_USERNAME/hofiz-bot.git
git push -u origin main
```

### 2. Railway loyihasi yaratish

1. [railway.app](https://railway.app) ga kiring
2. **New Project → Deploy from GitHub repo** → hofiz-bot ni tanlang
3. Loyiha yaratiladi — bu **Bot service** bo'ladi

---

### 3. PostgreSQL qo'shish

1. Railway dashboard → **+ Add Service → Database → PostgreSQL**
2. Railway avtomatik `DATABASE_URL` ni bot servisiga expose qiladi

---

### 4. Redis qo'shish

1. **+ Add Service → Database → Redis**
2. Railway avtomatik `REDIS_URL` ni expose qiladi

---

### 5. Bot service muhit o'zgaruvchilarni sozlash

Railway dashboard → Bot service → **Variables** bo'limiga quyidagilarni kiriting:

| O'zgaruvchi | Qiymat |
|---|---|
| `BOT_TOKEN` | BotFather dan |
| `ADMIN_IDS` | `123456789,987654321` |
| `BOT_MODE` | `polling` |
| `API_SECRET_KEY` | kuchli random kalit |
| `AUDD_API_KEY` | audd.io dan |
| `GENIUS_API_KEY` | genius.com/api dan |
| `API_BASE_URL` | API servis URL (6-bosqichdan keyin) |

> ⚠️ `DATABASE_URL` va `REDIS_URL` ni kiritmang — Railway o'zi qo'shadi!

---

### 6. API service qo'shish (Media yuklab olish)

1. **+ Add Service → GitHub repo** → yana hofiz-bot ni tanlang
2. Servis nomi: `api`
3. Service → **Settings → Build** → Dockerfile Path: `Dockerfile.api`
4. **Redeploy**
5. API servisda ham `API_SECRET_KEY` ni kiriting (bot bilan bir xil)
6. API servisning **public URL** ni nusxalab, bot servisida `API_BASE_URL` ga kiriting

---

### 7. Deploy tayyorligi tekshirish

Railway har ikkala servis uchun log ko'rsatadi:

```
Bot service log:
✅ Redis ulandi
✅ Database tayyor
🤖 Bot: @hofiz_bot

API service log:
INFO: Application startup complete.
```

---

## Narx taxmini

| Xizmat | Narx |
|---|---|
| Bot service | ~$3-5/oy |
| API service | ~$5-8/oy |
| PostgreSQL | ~$5/oy |
| Redis | ~$3/oy |
| **Jami** | **~$16-21/oy** |

Railway har oy $5 bepul kredit beradi. Kichik foydalanuvchi soni bo'lsa bepul ishlaydi.

---

## Foydali buyruqlar (Railway CLI)

```bash
# Railway CLI o'rnatish
npm i -g @railway/cli

# Login
railway login

# Loglarni ko'rish
railway logs --service bot
railway logs --service api

# O'zgaruvchilarni ko'rish
railway variables --service bot

# Qayta deploy
railway redeploy --service bot
```

---

## Muammolar va yechimlar

**Bot ishga tushmayapti?**
- `BOT_TOKEN` to'g'ri kiritilganini tekshiring
- `DATABASE_URL` Railway tomonidan qo'shilganini tekshiring

**Migratsiya xatosi?**
- Bot service logida alembic xatosini ko'ring
- `railway run --service bot alembic upgrade head` buyrug'ini bajaring

**API servis 503 qaytarmoqda?**
- `EXPOSE 8000` va `$PORT` to'g'ri sozlanganini tekshiring
- Health check: `https://api-xxx.railway.app/health`
