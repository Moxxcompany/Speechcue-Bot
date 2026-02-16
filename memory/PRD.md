# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
Analyze and setup the existing Speechcad Telegram IVR Bot codebase.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: SQLite (local dev) / PostgreSQL (production via Docker)
- **Cache/Queue**: Redis (localhost:6379)
- **Telegram**: pyTelegramBotAPI with webhook mode
- **Voice Provider**: Retell AI (retell-sdk 5.12.0) — migrated from Bland.ai
- **Wallet**: Internal PostgreSQL wallet + DynoPay crypto payments
- **Background Tasks**: Celery (4 periodic tasks) + Huey (2 on-demand tasks)
- **Languages**: English, Chinese, French, Hindi (438 translation keys)

## Core Apps
| App | Purpose |
|-----|---------|
| `bot/` | Telegram bot handlers, IVR flow builder, Retell integration, webhooks |
| `user/` | TelegramUser model (profile, language, subscription status) |
| `payment/` | Subscription plans, wallet, transactions, DTMF inbox |
| `TelegramBot/` | Django settings, URLs, Celery config |
| `translations/` | Multi-language support (EN/CN/FR/HI) |

## Key Integrations
- **Retell AI**: Agent management, phone calls, batch calls, voice listing, webhooks
- **DynoPay**: Crypto wallet & payment processing (BTC, ETH, USDT, LTC, DOGE, BCH, TRON)
- **Redis**: User language cache, Celery broker, Huey queue

## What's Been Implemented (Previous Sessions)
- [x] Full codebase setup + bot webhook
- [x] Retell AI migration from Bland.ai (22 functions)
- [x] Internal wallet + DynoPay crypto
- [x] Webhook-based call processing (replaced 3 polling tasks)
- [x] Celery worker + beat + Huey consumer
- [x] E2E Gap Analysis (10 gaps found and fixed)
- [x] Multi-language audit (438 keys, 8 hardcoded strings fixed)

## What's Been Done (Current Session - Jan 2026)
- [x] Analyzed full codebase structure and dependencies
- [x] Installed all Python dependencies (Django, Retell SDK, Celery, Redis, etc.)
- [x] Set up Redis server
- [x] Connected to Railway PostgreSQL (nozomi.proxy.rlwy.net:19535/railway)
- [x] Created .env with all environment variables (Telegram, Retell, DynoPay, Railway DB)
- [x] Ran all 129 database migrations successfully against Railway PostgreSQL
- [x] Seeded 10 subscription plans + overage pricing
- [x] Fixed missing `get_plan_price` utility function
- [x] Backend running and responding on port 8001
- [x] Verified external webhook endpoints (Retell + Telegram)
- [x] Real Telegram Bot Token configured (8125289128:AAG...)
- [x] DynoPay wallet integration configured (API key + wallet token)
- [x] Removed unused Bland.ai keys

## Environment Details
- **Backend**: http://localhost:8001 (uvicorn ASGI)
- **External URL**: https://bdb606ba-668c-463e-877d-5d068e1627fe.preview.emergentagent.com
- **Retell Webhook**: /api/webhook/retell
- **Telegram Webhook**: /api/telegram/webhook/
- **Admin**: http://localhost:8001/admin/ (admin/speechcadadmin1234)
- **Database**: Railway PostgreSQL (nozomi.proxy.rlwy.net:19535/railway)

## Prioritized Backlog
### P0 - Critical
- Set real Telegram Bot Token (API_TOKEN) to enable bot commands
- Purchase/configure Retell phone number for outbound calls
- Set Telegram webhook URL pointing to external endpoint

### P1 - High
- Configure Retell webhook URL on agents for call events
- Set up Celery worker + beat for background tasks
- Test full IVR flow: create flow → make call → receive webhook

### P2 - Medium
- Store call_analysis data (sentiment, summary) from Retell
- Recording playback feature
- Admin dashboard for tenant management
- Quo integration (complementary SMS/contacts)

### P3 - Low/Future
- Multi-tenancy architecture (shared schema with tenant_id)
- Per-tenant API keys
- US carrier registration for Quo SMS
