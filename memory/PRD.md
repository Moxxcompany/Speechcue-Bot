# Speechcad - PRD & Project Memory

## Original Problem Statement
User requested: "analyze and setup" — analyze the existing codebase and set it up to be runnable.
Then: update .env with real credentials, switch to PostgreSQL, configure webhooks.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn)
- **Database**: PostgreSQL on Railway (`nozomi.proxy.rlwy.net:19535/railway`)
- **Bot**: pyTelegramBotAPI (Telegram Bot) — Token verified working
- **Voice AI**: Retell AI SDK — API key verified working (200 OK)
- **Task Queue**: Celery + Redis (Railway Redis instance)
- **Payments**: DynoPay API + internal wallet system

## Pod URL
`https://f723c344-fa07-4ea8-924c-2345ee24681e.preview.emergentagent.com`

## Webhook URLs
- **Telegram Webhook**: `https://f723c344-fa07-4ea8-924c-2345ee24681e.preview.emergentagent.com/api/telegram/webhook/`
- **Retell Webhook**: `https://f723c344-fa07-4ea8-924c-2345ee24681e.preview.emergentagent.com/api/webhook/retell`
- **Call Details Webhook**: `https://f723c344-fa07-4ea8-924c-2345ee24681e.preview.emergentagent.com/call_details`

## Django Apps
1. **bot** - Core Telegram bot logic, IVR flow creation, call management, Retell AI integration
2. **payment** - Subscription plans, wallet, transactions, overage pricing, DynoPay
3. **user** - TelegramUser model with wallet balance

## What's Been Implemented
### Setup - 2026-02-16
- Installed all Python dependencies (Django 4.2.13, pyTelegramBotAPI, retell-sdk, celery, etc.)
- Created `/app/.env` with all real API keys and credentials
- Configured PostgreSQL via POSTGRES_URL (Railway)
- Ran Django migrations against PostgreSQL
- Backend running via supervisor on port 8001 (ASGI)
- All endpoints verified working (Retell 200 OK, Telegram token valid)

## Environment Variables Configured
- `API_TOKEN` - Telegram Bot Token (verified working)
- `RETELL_API_KEY` - Retell AI API Key (verified 200 OK)
- `POSTGRES_URL` - Railway PostgreSQL
- `REDIS_URL` - Railway Redis
- `DYNOPAY_BASE_URL`, `DYNOPAY_API_KEY`, `DYNOPAY_WALLET_TOKEN` - Payment gateway
- `webhook_url` - Pod external URL

## Prioritized Backlog
### P0 - Critical
- [x] Real API keys configured
- [x] PostgreSQL connected and migrated
- [ ] Set Telegram webhook to pod URL
- [ ] Start Celery worker + beat for background tasks

### P1 - Important  
- [ ] Verify DynoPay integration working
- [ ] Test full bot flow end-to-end
- [ ] Configure admin superuser

### P2 - Nice to Have
- [ ] Add web dashboard for monitoring
- [ ] Production deployment configuration
