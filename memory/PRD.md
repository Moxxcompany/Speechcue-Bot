# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. "analyze and setup" — Set up the existing Django codebase
2. "analyze how we can replace bland.ai with Retell AI" — Migration analysis
3. "list out the entire bot flow for users and features, explain how retell supports each" — Full feature mapping

## Architecture
- **Framework**: Django 4.2.13
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Task Queue**: Celery + Huey
- **Telegram Bot**: pyTelegramBotAPI (telebot)
- **Current Voice API**: Bland.ai → **Migrating to Retell AI**
- **Payments**: DynoPay (crypto), Tatum (crypto pricing)
- **Languages**: EN, CN, FR, HI

## What's Been Implemented
- [x] Full codebase setup (PostgreSQL, Redis, migrations, seed data)
- [x] Bland.ai → Retell AI migration analysis (RETELL_MIGRATION_ANALYSIS.md)
- [x] Complete bot flow documentation with Retell feature mapping (RETELL_BOT_FLOW_ANALYSIS.md)

## Key Documents
- `/app/RETELL_MIGRATION_ANALYSIS.md` — API endpoint mapping, code examples, env changes
- `/app/RETELL_BOT_FLOW_ANALYSIS.md` — Full user flow, 20 features mapped to Retell

## Migration Summary
- 20 features analyzed, ALL supported by Retell AI
- 22 functions in bot/views.py need rewriting
- 3 Celery tasks need updating (can be replaced with webhooks)
- Retell adds: recordings, post-call analysis, PII redaction, agent versioning

## Prioritized Backlog
### P0 - Implement Migration
- Install retell-sdk, update env/settings
- Create Retell service layer
- Migrate views.py functions
- Update tasks.py

### P1 - Leverage New Capabilities
- Replace polling with Retell webhooks
- Add call recording support
- Add post-call analysis to feedback
- Use max_call_duration_ms for free plan

### P2 - Enhancements
- Agent versioning for A/B testing
- Knowledge base integration
- PII redaction for compliance
