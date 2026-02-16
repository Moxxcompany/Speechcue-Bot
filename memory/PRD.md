# Speechcad - PRD & Project Memory

## Original Problem Statement
User requested: "analyze and setup" — analyze the existing codebase and set it up to be runnable.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn)
- **Database**: SQLite (fallback; PostgreSQL supported via env vars)
- **Bot**: pyTelegramBotAPI (Telegram Bot)
- **Voice AI**: Retell AI SDK (migrated from Bland.ai)
- **Task Queue**: Celery + Redis (django-celery-beat for periodic tasks)
- **Payments**: Crypto wallet-based (internal wallet system)

## Django Apps
1. **bot** - Core Telegram bot logic, IVR flow creation, call management, Retell AI integration
2. **payment** - Subscription plans, wallet, transactions, overage pricing
3. **user** - TelegramUser model with wallet balance

## Key Endpoints
- `/admin/` - Django admin
- `/api/telegram/webhook/` - Telegram webhook
- `/api/webhook/retell` - Retell AI webhook
- `/create_flow/` / `/view_flows/` - Flow management
- `/terms-and-conditions/` - Terms page
- `/call_details` - Call details webhook

## What's Been Implemented (Setup - 2026-02-16)
- Installed all Python dependencies (Django 4.2.13, pyTelegramBotAPI, retell-sdk, celery, etc.)
- Created `/app/.env` with placeholder API tokens
- Ran Django migrations (SQLite)
- Backend running via supervisor on port 8001 (ASGI)
- All Django endpoints responding correctly

## Environment Variables Needed (User Must Provide)
- `API_TOKEN` - Telegram Bot Token (from @BotFather)
- `RETELL_API_KEY` - Retell AI API Key
- `REDIS_URL` - Redis connection URL (for Celery)
- PostgreSQL credentials (optional, for production)

## Prioritized Backlog
### P0 - Critical
- [ ] User provides real Telegram Bot Token
- [ ] User provides real Retell AI API Key
- [ ] Set up Redis for Celery background tasks

### P1 - Important
- [ ] Configure PostgreSQL (for ArrayField support in FeedbackLogs/FeedbackDetails)
- [ ] Set up Celery worker and beat scheduler
- [ ] Configure webhook URLs for Telegram and Retell

### P2 - Nice to Have
- [ ] Add monitoring/logging
- [ ] Set up admin superuser
- [ ] Production deployment configuration

## Next Tasks
1. Get real API keys from user (Telegram, Retell)
2. Set up Redis and Celery if background tasks needed
3. Any feature additions or modifications requested
