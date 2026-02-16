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
- [x] Fixed missing `get_plan_price` utility function
- [x] Real Telegram Bot Token configured (8125289128:AAG...)
- [x] DynoPay wallet integration configured (API key + wallet token)
- [x] Telegram webhook set and verified
- [x] Celery worker + beat running (4 periodic tasks)
- [x] Huey consumer running (2 on-demand tasks)
- [x] All services using Railway Redis (metro.proxy.rlwy.net:40681)
- [x] **Profitability analysis** — identified all old plans were LOSS-making (-50% to -450%)
- [x] **New plan structure** — Starter/Pro/Business tiers (40-60% margin)
- [x] **DB updated** — 10 new plans seeded, overage raised to $0.35/min
- [x] **Pre-call gate** (`bot/call_gate.py`) — enforces 2-min wallet/plan balance before every call
- [x] **International rate table** — 50+ countries, 8 pricing regions ($0.45-$0.85/min)
- [x] **International billing** in webhooks — real-time wallet deduction on call_ended
- [x] **4 call initiation points** gated (single IVR, task-based, confirmed, batch)
- [x] **Real-time billing** — ActiveCall model tracks live calls, Celery monitor every 30s
- [x] **Pre-deduction** — 2-min wallet hold on call_started for wallet-billed calls
- [x] **Incremental billing** — wallet debited every 30 seconds during active calls
- [x] **Low balance warning** — Telegram message sent when wallet can't cover next minute
- [x] **Auto-termination** — calls force-ended via Retell API when wallet exhausted
- [x] **Reconciliation** — call_ended webhook settles final charge (refund overpay / charge shortfall)

## Environment Details
- **Backend**: http://localhost:8001 (uvicorn ASGI)
- **External URL**: https://setup-wizard-95.preview.emergentagent.com
- **Retell Webhook**: /api/webhook/retell
- **Telegram Webhook**: /api/telegram/webhook/
- **Admin**: http://localhost:8001/admin/ (admin/speechcadadmin1234)
- **Database**: Railway PostgreSQL (nozomi.proxy.rlwy.net:19535/railway)

## Subscription Plans (NEW — Jan 2026)
| Plan | Price | Validity | Bulk Min | Single IVR | Transfer | Support | Overage |
|------|-------|----------|----------|------------|----------|---------|---------|
| Free | $0 | 1d | 0 | 1 min | No | 24/7 | N/A |
| Starter | $15/$39/$99 | 1d/7d/30d | 30/80/250 | 10/30/60 | No | 24/7 | $0.35/m |
| Pro | $25/$69/$179 | 1d/7d/30d | 50/150/500 | 20/50/100 | Yes | Priority | $0.35/m |
| Business | $45/$119/$299 | 1d/7d/30d | 100/350/1000 | 30/80/200 | Yes | Premium | $0.35/m |

## International Rates (wallet-deducted per-minute)
| Region | Rate |
|--------|------|
| US/Canada | Plan included |
| UK/W.Europe/India/China/SE Asia | $0.45/min |
| Japan/Australia/S.Korea | $0.55/min |
| Middle East | $0.60/min |
| Latin America | $0.65/min |
| Rest of World | $0.70/min |
| Africa | $0.85/min |

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
