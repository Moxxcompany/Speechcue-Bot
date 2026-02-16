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
- **Database**: PostgreSQL 17.7 on Railway
- **Bot**: pyTelegramBotAPI — @Speechcuebot
- **Voice AI**: Retell AI SDK (authenticated)
- **Task Queue**: Celery + Redis (Railway Redis)
- **Payments**: DynoPay crypto + internal wallet system

## Webhook URLs (live on pod)
- **Retell Voice**: `https://<pod>.preview.emergentagent.com/api/webhook/retell`
- **Supervisor DTMF**: `https://<pod>.preview.emergentagent.com/api/dtmf/supervisor-check`
- **Inbound SMS**: `https://<pod>.preview.emergentagent.com/api/webhook/sms`
- **Telegram**: `https://<pod>.preview.emergentagent.com/api/telegram/webhook/`
- **Time Check**: `https://<pod>.preview.emergentagent.com/api/time-check`

## What's Been Implemented

### Previous Sessions (2026-02-16)
- Full environment setup, PostgreSQL migration, real API keys
- CallerIds validation, agent binding on purchase, crypto auto-purchase
- Real-time DTMF streaming, supervisor approval, SMS inbox, recording delivery
- Voicemail/forwarding settings, lint cleanup

### Current Session — Real Credentials Setup (2026-01-XX)
- **Updated .env** with all real credentials (Telegram, Retell, PostgreSQL, Redis, DynoPay)
- **PostgreSQL connected**: Railway PostgreSQL 17.7 — 10 plans, 3 users, all migrations applied
- **Redis connected**: Railway Redis — ping OK
- **Retell API authenticated**: 200 OK on voice listing
- **Telegram webhook set**: `setWebhook` → pod URL, bot commands registered (/start, /support)
- **All webhook endpoints verified** via external URL (100% test pass rate)

## Connected Services Status
| Service | Status | Details |
|---------|--------|---------|
| PostgreSQL | ✅ Connected | Railway, 17.7, 10 plans, 3 users |
| Redis | ✅ Connected | Railway Redis |
| Retell AI | ✅ Authenticated | Voice list returns 200 |
| Telegram Bot | ✅ Active | @Speechcuebot, webhook set |
| DynoPay | ✅ Configured | Crypto payments ready |

## Test Results (Iteration 3)
- Backend: **100%** (9/9 tests passed)
- All webhook endpoints responding correctly
- Database and cache connections verified

## Prioritized Backlog
### P0 - All Complete ✅
- [x] Set real API tokens ✅
- [x] Set Telegram webhook to pod URL ✅
- [x] Celery worker + beat running with auto-start via server.py ✅
- [x] Inbound call billing ✅
- [x] After-hours conditional routing ✅
- [x] Retell agent prompt auto-update ✅

### P1 - Deferred
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Web admin dashboard
- [ ] Production deployment hardening
