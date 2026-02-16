# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. Analyze and setup the existing Django codebase
2. Analyze Bland.ai → Retell AI migration
3. Full bot flow documentation with Retell mapping
4. Configure Telegram bot webhook
5. Remove DynoPay wallet, build internal wallet, keep DynoPay crypto
6. Implement Retell AI migration

## Architecture
- **Framework**: Django 4.2.13 (ASGI/uvicorn on port 8001)
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Telegram Bot**: @Speechcuebot via webhook
- **Wallet**: Internal PostgreSQL (credit/debit/refund)
- **Crypto Payments**: DynoPay API (master wallet token)
- **Voice API**: Retell AI (retell-sdk 5.12.0)

## What's Been Implemented
- [x] Full codebase setup
- [x] Bot token + webhook configured
- [x] Email/phone onboarding steps removed
- [x] Internal wallet system + DynoPay crypto payments
- [x] **RETELL AI MIGRATION COMPLETE:**
  - bot/views.py: All 22 functions migrated (agents, calls, voices, batch, stop, transcripts)
  - bot/retell_service.py: Singleton Retell client
  - bot/tasks.py: check_call_status & call_status_free_plan use Retell
  - bot/webhooks.py: Handles Retell webhook events
  - bot/keyboard_menus.py: Voice filtering updated for Retell format
  - Retell API verified: 182 voices, 2 agents loaded, webhooks working

## Retell AI Migration Details
### Files Changed
| File | Changes |
|------|---------|
| bot/views.py | Complete rewrite — all Bland.ai → Retell SDK |
| bot/retell_service.py | New — Retell client singleton |
| bot/tasks.py | check_call_status, call_status_free_plan → Retell |
| bot/webhooks.py | Retell webhook event format |
| bot/keyboard_menus.py | Voice filter for Retell list format |
| TelegramBot/settings.py | Added RETELL_API_KEY |
| .env | Added RETELL_API_KEY |
| requirements.txt | Added retell-sdk==5.12.0 |

## Prioritized Backlog
### P0 - Testing
- Full bot onboarding flow test
- IVR flow creation test
- Call placement test (needs Retell phone number)

### P1 - Retell Phone Number
- Purchase/import number in Retell dashboard
- Configure as from_number for outbound calls

### P2 - Enhancements
- Webhook-based call monitoring (replace Celery polling)
- Call recording URL support
- Post-call analysis (sentiment, summary)
