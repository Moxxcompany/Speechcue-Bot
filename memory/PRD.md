# Speechcad - PRD & Project Memory

## Original Problem Statement
1. Analyze and setup the existing Django Telegram Bot codebase
2. Update .env with real credentials (Telegram, Retell, PostgreSQL, Redis, DynoPay)
3. Analyze Retell caller ID, phone number purchasing, call forwarding, subscription payments
4. Implement fixes: CallerIds validation, agent binding on purchase, crypto auto-purchase
5. Implement: Real-time DTMF supervisor control, SMS inbox, recording delivery, voicemail/forwarding
6. Fix all lint errors and clean up code gaps

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: SQLite (fallback; PostgreSQL ready via POSTGRES_URL env)
- **Bot**: pyTelegramBotAPI (Telegram Bot)
- **Voice AI**: Retell AI SDK
- **Task Queue**: Celery + Redis (when Redis URL is configured)
- **Payments**: DynoPay crypto + internal wallet system

## Webhook URLs (for Retell Dashboard)
- **Retell Voice**: `/api/webhook/retell`
- **Supervisor DTMF Check**: `/api/dtmf/supervisor-check`
- **Inbound SMS**: `/api/webhook/sms`
- **Telegram**: `/api/telegram/webhook/`
- **Time Check**: `/api/time-check`

## What's Been Implemented

### Previous Sessions (2026-02-16)
- Full environment setup, PostgreSQL migration, real API keys
- CallerIds validation, agent binding on purchase, crypto auto-purchase
- Real-time DTMF streaming via transcript_updated
- Supervisor DTMF approval (single calls only)
- SMS Inbox delivery, DTMF node loop-back, recording delivery
- Voicemail/forwarding settings per purchased number
- All files pass lint cleanly

### Current Session — Setup & Analysis (2026-01-XX)
- **Installed all Python dependencies** (Django, Retell SDK, pyTelegramBotAPI, Celery, etc.)
- **Created .env** with placeholder credentials for Telegram, Retell, DynoPay, Redis
- **Ran database migrations** (SQLite fallback) — all 3 pending migrations applied
- **Backend running** on uvicorn port 8001 via supervisor ✅
- **Frontend placeholder** created (React app) so supervisor doesn't crash
- **Admin superuser** exists (admin / admin123)
- **Subscription plans seeded**: 10 plans (Free, Prime, Elite, etc.)
- **All webhook endpoints verified working**:
  - `/api/webhook/retell` → 200 ✅
  - `/api/webhook/sms` → 200 ✅
  - `/api/dtmf/supervisor-check` → 200 ✅
  - `/api/time-check` → 200 ✅

## Current Status
- Backend: RUNNING ✅
- Frontend: RUNNING (placeholder React app)
- Database: SQLite (all migrations applied)
- Bot: Token is placeholder — needs real Telegram Bot token to function
- Retell: API key is placeholder — needs real key for voice API calls
- Redis/Celery: Not running (needs Redis URL)

## Environment Variables Needed (Real Values)
| Variable | Current | Needed |
|----------|---------|--------|
| `API_TOKEN` | Placeholder | Real Telegram Bot token |
| `RETELL_API_KEY` | Placeholder | Real Retell API key |
| `DYNOPAY_API_KEY` | Placeholder | Real DynoPay key |
| `DYNOPAY_WALLET_TOKEN` | Placeholder | Real wallet token |
| `REDIS_URL` | localhost | Real Redis URL (for Celery) |
| `POSTGRES_URL` | Not set | PostgreSQL URL (optional, SQLite works) |

## Prioritized Backlog
### P0 - Immediate
- [ ] Set real API tokens (Telegram, Retell, DynoPay)
- [ ] Set Telegram webhook to pod URL
- [ ] Start Celery worker + beat (requires Redis)

### P1 - Remaining
- [ ] Inbound call billing (charge wallet for inbound minutes)
- [ ] After-hours conditional routing
- [ ] Retell agent prompt auto-update when voicemail/forwarding toggled

### P2 - Deferred
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Web admin dashboard
- [ ] Production PostgreSQL migration
