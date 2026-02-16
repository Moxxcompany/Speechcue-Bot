# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. Analyze and setup the existing Django codebase
2. Analyze Bland.ai → Retell AI migration
3. Full bot flow documentation with Retell mapping
4. Configure Telegram bot webhook
5. Remove DynoPay wallet, build internal wallet, keep DynoPay crypto
6. Implement Retell AI migration
7. Replace Celery polling with Retell real-time webhooks
8. Set up Celery worker for background tasks

## Architecture
- **Framework**: Django 4.2.13 (ASGI/uvicorn on port 8001)
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Telegram Bot**: @Speechcuebot via webhook
- **Wallet**: Internal PostgreSQL (credit/debit/refund)
- **Crypto Payments**: DynoPay API (master wallet token)
- **Voice API**: Retell AI (retell-sdk 5.12.0)
- **Call Events**: Real-time via Retell webhooks
- **Background Tasks**: Celery (4 periodic) + Huey (2 on-demand)

## What's Been Implemented
- [x] Full codebase setup
- [x] Bot token + webhook configured
- [x] Email/phone onboarding steps removed
- [x] Internal wallet system + DynoPay crypto payments
- [x] Retell AI migration (all 22 functions)
- [x] Webhook-based call processing (replaces 3 polling tasks)
- [x] **Celery worker + beat + Huey consumer all running:**
  - charge_user_for_additional_minutes (every 5 min)
  - notify_users (every 10 min)
  - check_subscription_status (every 1 hour)
  - send_scheduled_ivr_calls (every 1 min)
  - execute_bulk_ivr (Huey, on-demand)
  - send_reminder (Huey, on-demand)

## Background Task Architecture
```
Celery Beat (scheduler) → Celery Worker (4 processes)
  ├── charge_user_for_additional_minutes (5 min)
  ├── notify_users (10 min)
  ├── check_subscription_status (1 hour)
  └── send_scheduled_ivr_calls (1 min)

Huey Consumer (4 threads)
  ├── execute_bulk_ivr (on-demand, triggered by scheduled campaigns)
  └── send_reminder (on-demand, triggered before scheduled calls)

Retell Webhooks (real-time, instant)
  ├── call_started → update call status
  ├── call_ended → duration billing + DTMF + overage
  └── call_analyzed → sentiment + summary
```

## Prioritized Backlog
### P0 - Testing
- Full bot onboarding + call flow e2e test
- Need Retell phone number for outbound calls

### P1 - Production Hardening
- Supervisor configs for Celery/Huey (auto-restart)
- Logging aggregation
- Error alerting

### P2 - Enhancements
- Store call_analysis in new model
- Call recording playback in bot
- Admin dashboard
