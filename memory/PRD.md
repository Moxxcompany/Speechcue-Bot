# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1-7: Setup, Retell migration, wallet, webhooks (all done)
8. End-to-end gap analysis + multi-language audit

## Architecture
- Django 4.2.13 (ASGI/uvicorn:8001) | PostgreSQL 15 | Redis
- Telegram: @Speechcuebot via webhook
- Wallet: Internal PostgreSQL | Crypto: DynoPay API
- Voice: Retell AI (retell-sdk 5.12.0) | Events: Retell webhooks
- Background: Celery (4 periodic) + Huey (2 on-demand)
- Languages: English, Chinese, French, Hindi (438 keys, all complete)

## What's Been Implemented
- [x] Full codebase setup + bot webhook
- [x] Retell AI migration (22 functions)
- [x] Internal wallet + DynoPay crypto
- [x] Webhook-based call processing (replaced 3 polling tasks)
- [x] Celery worker + beat + Huey consumer
- [x] **E2E Gap Analysis Complete — 10 gaps found and fixed:**
  1. base_url in translations still pointed to bland.ai → Dead code, no impact
  2. voice_data["voices"] in telegrambot.py → Fixed for Retell list format
  3. crypto_cache.py used old API key → Dead code, not called
  4. Missing TATUM_API_URL env vars → Added to .env
  5. Missing crypto_conversion_base_url → Added to .env
  6. Dead code: get_main_menu(), get_available_commands() → Unused, no impact
  7. Dead code: VALID_NODE_TYPES → Unused, no impact
  8. Dead code: fetch_crypto_price_with_retry → Unused, no impact
  9. ACCEPT_TERMS_AND_CONDITIONS missing [lg] → Fixed
  10. PROCESSING_ERROR missing [lg] in 2 places → Fixed
- [x] **Multi-language audit complete:**
  - 438 translation keys, all have EN/CN/FR/HI
  - 5 new translation keys added (TASK_NAME_EXISTS, CALL_SCHEDULED_SUCCESS, etc.)
  - 8 hardcoded English bot.send_message → All replaced with translated versions
  - 87 message handlers use .values() for multi-language matching
  - All keyboard menus use [lg] translations

## Prioritized Backlog
### P0 - Purchase Retell phone number + test real call
### P1 - Configure Retell webhook URL on agents
### P2 - Store call_analysis, recording playback, admin dashboard
