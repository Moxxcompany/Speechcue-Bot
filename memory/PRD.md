# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. Analyze and setup the existing Django codebase
2. Analyze Bland.ai → Retell AI migration
3. Full bot flow documentation with Retell mapping
4. Configure Telegram bot webhook
5. Remove DynoPay wallet, build internal wallet, keep DynoPay crypto
6. Implement Retell AI migration
7. Replace Celery polling with Retell real-time webhooks

## Architecture
- **Framework**: Django 4.2.13 (ASGI/uvicorn on port 8001)
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Telegram Bot**: @Speechcuebot via webhook
- **Wallet**: Internal PostgreSQL (credit/debit/refund)
- **Crypto Payments**: DynoPay API (master wallet token)
- **Voice API**: Retell AI (retell-sdk 5.12.0)
- **Call Events**: Real-time via Retell webhooks (no polling)

## What's Been Implemented
- [x] Full codebase setup
- [x] Bot token + webhook configured
- [x] Email/phone onboarding steps removed
- [x] Internal wallet system + DynoPay crypto payments
- [x] Retell AI migration (all 22 functions)
- [x] **Webhook-based call processing:**
  - call_started → updates call status in DB
  - call_ended → processes duration, billing, DTMF, overage tracking
  - call_analyzed → captures sentiment, summary (new Retell capability)
  - 3 Celery polling tasks deprecated (check_call_status, call_status_free_plan, process_call_logs)

## Webhook Architecture
```
Retell AI → POST /api/webhook/retell → bot/webhooks.py
  ├── call_started  → Update BatchCallLogs/CallLogsTable status
  ├── call_ended    → Duration billing + DTMF extraction + overage tracking
  └── call_analyzed → Sentiment + summary logging
```
Retell webhook URL: https://<domain>/api/webhook/retell

## Prioritized Backlog
### P0 - Testing
- Full bot onboarding flow test
- IVR call test (needs Retell phone number)

### P1 - Retell Dashboard Config
- Purchase phone number in Retell
- Configure webhook URL on agents
- Set max_call_duration_ms for free plan agents

### P2 - Enhancements
- Store call_analysis (sentiment/summary) in new model
- Call recording playback in bot
- Admin dashboard
