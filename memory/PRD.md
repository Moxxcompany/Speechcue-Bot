# PRD - Telegram IVR Bot

## Problem Statement
Analyze and set up an existing Django-based Telegram Bot codebase for IVR (Interactive Voice Response) management, integrate Quo as a voice provider, implement multi-tenancy, and document findings.

## Architecture
- **Backend**: Django 4.2.13 (Python 3.11)
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis
- **Task Queue**: Celery + django-celery-beat, Huey
- **Bot Framework**: pyTelegramBotAPI
- **External APIs**: Bland.ai (IVR calls), DynoPay (crypto payments), Tatum (crypto rates), Quo (phone/messaging)

## Core Features
- Telegram Bot for IVR call management (single/bulk)
- Multi-language support (English, Hindi, Chinese, French)
- Subscription plans with crypto payments (USDT)
- Campaign management with batch calls
- DTMF input handling
- AI-assisted task flows (pathways)
- Scheduled calls & reminders
- User wallet management
- Call logging & duration tracking

## Django Apps
- `bot` - Core bot logic, views, webhooks, call management
- `user` - Telegram user model
- `payment` - Subscriptions, transactions, wallets, DTMF inbox
- `translations` - Multi-language support

## What's Been Implemented

### Setup (Jan 2026)
- Installed PostgreSQL 15, Redis, all Python dependencies
- Created `.env` with database config and placeholder API keys
- Ran all migrations (38 tables created)
- Seeded 10 subscription plans
- Fixed bot_config.py to gracefully handle missing Telegram API token
- Django server verified to start without errors

### Quo Integration Analysis (Feb 2026)
- Crawled and documented full Quo API (calls, messages, contacts, webhooks, phone numbers)
- Verified Quo API key works (workspace: Moxx Technologies, phone: +18886033870)
- Produced comprehensive gap analysis: Bland.ai vs Quo
- **Key Finding**: Quo CANNOT replace Bland.ai (no outbound calls, no IVR pathways, no AI voice agent)
- **Recommendation**: Use Quo as COMPLEMENTARY provider (SMS, contacts, caller ID, call monitoring)
- Designed multi-tenancy architecture (shared schema with tenant_id)
- Full analysis document: `/app/QUO_INTEGRATION_ANALYSIS.md`

## API Keys
- `API_TOKEN` - Telegram Bot token (placeholder)
- `BLAND_API_KEY` - Bland.ai API key for IVR calls (placeholder)
- `QUO_API_KEY` - Quo API key: `tul7jVf2oQHGPMp211neCYcWoKMxAOzt` (verified working)
- `x-api-key` - DynoPay API key (placeholder)

## Quo Workspace Details
- Phone Number: +18886033870 (ID: PNHNMitFtw)
- Owner: Moxx Technologies (ID: USSX7fbpdt)
- US/CA Calling: Unrestricted
- Messaging: Restricted (needs carrier registration)

## Next Action Items
- **Decision Required**: Confirm integration strategy (Quo as complementary vs full provider replacement)
- Implement Quo client module (`bot/quo_client.py`) based on chosen strategy
- Begin multi-tenancy Phase 1 (Tenant model + migration)

## Backlog
- P0: Implement chosen Quo integration strategy
- P0: Multi-tenancy Phase 1 (Tenant model, nullable FKs)
- P1: Multi-tenancy Phase 2-6 (backfill, constraints, query updates)
- P1: Complete US carrier registration for Quo SMS
- P2: Configure real API keys and verify bot functionality
- P2: Set up Celery workers for async task processing
