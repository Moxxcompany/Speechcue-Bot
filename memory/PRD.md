# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. Analyze and setup the existing Django codebase
2. Analyze Bland.ai → Retell AI migration
3. Full bot flow documentation with Retell mapping
4. Configure Telegram bot webhook
5. Remove DynoPay, build internal wallet system

## Architecture
- **Framework**: Django 4.2.13 (ASGI/uvicorn on port 8001)
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Task Queue**: Celery + Huey
- **Telegram Bot**: @Speechcuebot via webhook
- **Wallet**: Internal PostgreSQL wallet (replaced DynoPay)
- **Voice API**: Bland.ai (pending Retell AI migration)

## What's Been Implemented
- [x] Full codebase setup (PostgreSQL, Redis, migrations, seed data)
- [x] Bland.ai → Retell AI migration analysis docs
- [x] Bot token configured, webhook verified
- [x] Email/phone onboarding steps removed
- [x] **DynoPay completely removed** — internal wallet system built
- [x] Wallet operations: credit, debit, refund with atomic transactions
- [x] Full audit trail via WalletTransaction model
- [x] All 6 DynoPay API calls replaced with local DB operations
- [x] tasks.py updated (overage billing, auto-renewal)
- [x] All wallet operations tested and verified

## Internal Wallet System
### Functions (payment/views.py)
- `setup_user()` — creates user with $0 balance (no external API)
- `check_user_balance()` — reads from TelegramUser.wallet_balance
- `credit_wallet()` — adds funds (top-ups, deposits)
- `debit_wallet()` — deducts funds (subscriptions, overage)
- `refund_wallet()` — credits back with REFUND transaction type
- `credit_wallet_balance()` — backward-compatible debit wrapper

### Refund Flow
`refund_wallet(user_id, amount, description)` → atomically credits wallet + creates REFUND transaction log

## Prioritized Backlog
### P0 - Retell AI Migration
- Install retell-sdk, create service layer
- Migrate 22 API functions in views.py
- Update tasks.py and webhooks.py

### P1 - Crypto Payment Integration
- Replace DynoPay crypto with BlockBee/CoinGate
- Currently stubbed in create_crypto_payment()

### P2 - Enhancements
- Admin dashboard for wallet management
- Transaction history in bot UI
