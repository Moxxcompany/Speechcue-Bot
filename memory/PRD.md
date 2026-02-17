# Speechcue Telegram Bot - PRD

## Original Problem Statement
Setup the Speechcue Telegram bot application with all environment variables configured and webhook pointing to the current pod URL.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn)
- **Telegram Bot**: pyTelegramBotAPI (webhook mode)
- **Voice AI**: Retell AI SDK
- **Payments**: DynoPay (crypto) + Internal Wallet (PostgreSQL)
- **Database**: PostgreSQL on Railway (nozomi.proxy.rlwy.net:19535)
- **Cache/Broker**: Redis on Railway (metro.proxy.rlwy.net:40681)
- **Task Queue**: Celery + Celery Beat (with django-celery-beat scheduler)

## Core Features
- IVR call script creation and management via Telegram bot
- Single and bulk voice calls via Retell AI
- DTMF input collection with supervisor approval flow
- Subscription plans (Free, Starter, Pro, Business)
- Internal wallet system with crypto top-up (DynoPay)
- Phone number purchasing and management (Retell)
- SMS inbox, call recordings, call history
- Multi-language support (English, Hindi, Chinese, French)
- Campaign scheduling and management

## What's Been Implemented (Feb 17, 2026)
- Created `/app/.env` and `/app/backend/.env` with all credentials
- Configured webhook_url to current pod: `https://quickstart-43.preview.emergentagent.com`
- Installed all Python dependencies from requirements.txt
- Verified PostgreSQL and Redis connections
- Ran Django migrations (all applied)
- Set Telegram webhook via API
- Backend running on port 8001 (supervisor managed)
- Celery worker + beat running (auto-started by server.py)
- All webhook endpoints verified: Telegram, Retell, DTMF, SMS, Time-check

## Webhook Endpoints
| Endpoint | URL Path | Status |
|---|---|---|
| Telegram | `/api/telegram/webhook/` | Active |
| Retell AI | `/api/webhook/retell` | Active |
| DTMF Supervisor | `/api/dtmf/supervisor-check` | Active |
| SMS Inbound | `/api/webhook/sms` | Active |
| Time Check | `/api/time-check` | Active |

## User Personas
- **Bot Admin**: Manages IVR flows, campaigns, phone numbers
- **End User**: Uses Telegram bot to create call scripts and make calls

## Backlog
- P0: None (all core features working)
- P1: Configure Retell webhook URL in Retell dashboard to point to `/api/webhook/retell`
- P2: Update TERMS_AND_CONDITIONS_URL and CHANNEL_LINK to actual values
- P2: Add /api prefix to terms-and-conditions route for ingress compatibility
