# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
User requested: "analyze and setup" for the existing codebase, then "analyze how we can replace bland.ai with Retell AI"

## Architecture
- **Framework**: Django 4.2.13
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Task Queue**: Celery + Huey (django-celery-beat for periodic tasks)
- **Telegram Bot**: pyTelegramBotAPI (telebot)
- **Current Voice API**: Bland.ai (IVR/Voice) → **Migrating to Retell AI**
- **Payments**: DynoPay (crypto payments), Tatum (crypto pricing)
- **Languages**: English, Chinese, French, Hindi

## What's Been Implemented
- [x] Full codebase analysis completed
- [x] PostgreSQL 15 installed and configured
- [x] Redis server installed and running
- [x] Django migrations applied (all 80+ migrations)
- [x] 10 subscription plans seeded
- [x] Django admin superuser created (admin/speechcadadmin1234)
- [x] Comprehensive Bland.ai → Retell AI migration analysis (`RETELL_MIGRATION_ANALYSIS.md`)

## Migration Analysis Summary (Bland.ai → Retell AI)
- **22 functions** in bot/views.py need rewriting
- **2 celery tasks** in bot/tasks.py need field mapping updates
- **Webhook handler** needs Retell payload format
- **Key concept**: Bland pathways → Retell agents with conversation flow
- **Critical differences**: Status values, timestamp formats, transcript structure, auth header format
- Full analysis: `/app/RETELL_MIGRATION_ANALYSIS.md`

## Prioritized Backlog
### P0 - Migration Implementation
- Install retell-sdk, update env vars
- Create Retell service layer
- Migrate all 22 API functions in bot/views.py
- Update tasks.py call status polling
- Update webhook handler

### P1 - Testing & Validation
- Test each migrated function
- Verify call status monitoring
- Test batch calling
- End-to-end Telegram bot flow testing

### P2 - Enhancements
- Migrate from polling to Retell webhooks
- Add recording URL support (new capability from Retell)
- Add post-call analysis (sentiment, summary)
