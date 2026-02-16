# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
User requested: "analyze and setup" for the existing codebase.

## Architecture
- **Framework**: Django 4.2.13
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Task Queue**: Celery + Huey (django-celery-beat for periodic tasks)
- **Telegram Bot**: pyTelegramBotAPI (telebot)
- **External APIs**: Bland.ai (IVR/Voice), DynoPay (crypto payments), Tatum (crypto pricing)
- **Languages**: English, Chinese, French, Hindi

## Core Modules
| Module | Description |
|--------|-------------|
| `bot/` | Telegram bot handlers, IVR flow management, pathway nodes/edges |
| `user/` | TelegramUser model with encrypted tokens |
| `payment/` | Subscription plans, wallet, crypto payments, overage billing |
| `translations/` | Multi-language support (EN, CN, FR, HI) |
| `TelegramBot/` | Django settings, URLs, constants, Celery config |

## User Personas
- **IVR Flow Creator**: Builds IVR call flows using Bland.ai pathways
- **Bulk Caller**: Manages campaigns with scheduled batch calls
- **Subscriber**: Manages subscription plans, wallet top-ups via crypto

## What's Been Implemented (Jan 2026)
- [x] Full codebase analysis completed
- [x] PostgreSQL 15 installed and configured
- [x] Redis server installed and running
- [x] Django migrations applied (all 80+ migrations)
- [x] 10 subscription plans seeded (Free, Prime, Elite, Ultra)
- [x] Overage pricing configured ($0.05/min)
- [x] Django admin superuser created (admin/speechcadadmin1234)
- [x] .env file created with placeholder API keys
- [x] Django system check passing (0 issues)

## Required API Keys (placeholders currently)
- `API_TOKEN` - Telegram Bot API token
- `BLAND_API_KEY` - Bland.ai API key for IVR
- `x-api-key` - DynoPay API key for payments
- `x_api_tatum` - Tatum API key for crypto pricing

## Prioritized Backlog
### P0 - Critical
- Replace placeholder API keys with real credentials
- Configure webhook URL for production
- Set up Celery worker for background tasks

### P1 - Important
- QUO SMS integration (per QUO_INTEGRATION_ANALYSIS.md)
- Production deployment configuration (DEBUG=False, ALLOWED_HOSTS)

### P2 - Nice to Have
- Add unit tests
- Rate limiting on webhook endpoints
- Monitoring/alerting setup

## Next Tasks
1. User to provide real API tokens (Telegram, Bland.ai, DynoPay, Tatum)
2. Configure Celery worker and beat scheduler
3. Set up Telegram webhook or polling mode
4. Production security hardening
