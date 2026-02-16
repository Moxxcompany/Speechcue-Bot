# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. "analyze and setup" — Set up the existing Django codebase
2. "analyze how we can replace bland.ai with Retell AI" — Migration analysis
3. "list out the entire bot flow and features, explain how retell supports each"
4. "configure bot token and ensure webhook is working"

## Architecture
- **Framework**: Django 4.2.13 (served via ASGI/uvicorn on port 8001)
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Task Queue**: Celery + Huey
- **Telegram Bot**: pyTelegramBotAPI via webhook
- **Webhook URL**: https://87b95f0b-b918-4d83-a2b3-889e55b083f2.preview.emergentagent.com/api/telegram/webhook/
- **Bot**: @Speechcuebot (8125289128)
- **Current Voice API**: Bland.ai → Migrating to Retell AI
- **Payments**: DynoPay (crypto), Tatum (crypto pricing)

## What's Been Implemented
- [x] Full codebase setup (PostgreSQL, Redis, migrations, seed data)
- [x] Bland.ai → Retell AI migration analysis
- [x] Complete bot flow documentation with Retell feature mapping
- [x] Bot token configured (8125289128:AAG_PqL3...)
- [x] Telegram webhook set and verified (0 pending, no errors)
- [x] Django ASGI bridge (server.py) for uvicorn compatibility
- [x] Webhook endpoint at /api/telegram/webhook/
- [x] End-to-end test: /start command → user created in DB

## Key Documents
- `/app/RETELL_MIGRATION_ANALYSIS.md` — API endpoint mapping, code examples
- `/app/RETELL_BOT_FLOW_ANALYSIS.md` — Full user flow, 20 features mapped

## Prioritized Backlog
### P0 - Implement Retell AI Migration
- Install retell-sdk, update env/settings
- Create Retell service layer
- Migrate views.py functions
- Update tasks.py and webhooks.py

### P1 - Production Readiness
- Set up Celery worker + beat scheduler
- Configure real DynoPay/Tatum keys
- Production security hardening

### P2 - Enhancements
- Replace polling with Retell webhooks
- Add call recording support
- Post-call analysis for feedback
