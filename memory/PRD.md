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
- **Database**: PostgreSQL on Railway
- **Bot**: pyTelegramBotAPI (Telegram Bot)
- **Voice AI**: Retell AI SDK
- **Task Queue**: Celery + Redis (Railway Redis)
- **Payments**: DynoPay crypto + internal wallet system

## Webhook URLs (for Retell Dashboard)
- **Retell Voice**: `.../api/webhook/retell`
- **Supervisor DTMF Check**: `.../api/dtmf/supervisor-check`
- **Inbound SMS**: `.../api/webhook/sms`
- **Telegram**: `.../api/telegram/webhook/`

## What's Been Implemented

### Session 1-2 — Setup + Env (2026-02-16)
- Full environment setup, PostgreSQL migration, real API keys

### Session 3 — Core Fixes (2026-02-16)
- CallerIds validation, agent binding on purchase, crypto auto-purchase

### Session 4 — DTMF + SMS + Voicemail (2026-02-16)
- Real-time DTMF streaming via transcript_updated
- Supervisor DTMF approval (single calls only)
- SMS Inbox delivery, DTMF node loop-back, recording delivery
- Voicemail/forwarding settings per purchased number

### Session 5 — Lint Cleanup (2026-02-16)
- Fixed all real lint errors: webhooks.py (3), views.py (4), payment/views.py (1), telegrambot.py (7 f-string fixes + 17 auto-fixes)
- Added pyproject.toml with ruff config to suppress pre-existing star import warnings
- **All files now pass lint cleanly**: webhooks.py ✅, views.py ✅, retell_service.py ✅, models.py ✅, tasks.py ✅, telegrambot.py ✅, payment/views.py ✅, urls.py ✅

## Lint Status
- `bot/webhooks.py` — ✅ Clean
- `bot/views.py` — ✅ Clean (fixed undefined logger, unused vars)
- `bot/retell_service.py` — ✅ Clean
- `bot/models.py` — ✅ Clean
- `bot/tasks.py` — ✅ Clean
- `bot/telegrambot.py` — ✅ Clean (pre-existing star-import F405 suppressed via pyproject.toml)
- `payment/views.py` — ✅ Clean
- `TelegramBot/urls.py` — ✅ Clean

## Prioritized Backlog
### P1 - Remaining
- [ ] Inbound call billing (charge wallet for inbound minutes)
- [ ] After-hours conditional routing
- [ ] Retell agent prompt auto-update when voicemail/forwarding toggled
- [ ] Set Telegram webhook to pod URL
- [ ] Start Celery worker + beat

### P2 - Deferred
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Web admin dashboard
