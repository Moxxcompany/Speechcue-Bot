# Speechcad - PRD & Project Memory

## Original Problem Statement
1. Analyze and setup the existing Django Telegram Bot codebase
2. Update .env with real credentials (Telegram, Retell, PostgreSQL, Redis, DynoPay)
3. Analyze Retell caller ID requirements, phone number purchasing, call forwarding, subscription payments
4. Implement fixes: CallerIds validation, agent binding on purchase, crypto auto-purchase

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: PostgreSQL on Railway (`nozomi.proxy.rlwy.net:19535/railway`)
- **Bot**: pyTelegramBotAPI (Telegram Bot) — Token verified
- **Voice AI**: Retell AI SDK — API key verified (200 OK)
- **Task Queue**: Celery + Redis (Railway Redis)
- **Payments**: DynoPay crypto + internal wallet system

## Pod URL
`https://f723c344-fa07-4ea8-924c-2345ee24681e.preview.emergentagent.com`

## Webhook URLs
- **Telegram**: `.../api/telegram/webhook/`
- **Retell**: `.../api/webhook/retell`
- **Crypto Deposit**: `.../webhook/crypto_deposit`
- **Crypto Transaction**: `.../webhook/crypto_transaction`
- **Call Details**: `.../call_details`

## What's Been Implemented

### Session 1 — Setup (2026-02-16)
- Installed all Python dependencies, created .env, ran migrations (SQLite)
- Backend running via supervisor

### Session 2 — Env Update (2026-02-16)
- Updated .env with real keys (Telegram, Retell, PostgreSQL, Redis, DynoPay)
- Configured Django to parse POSTGRES_URL format
- Migrated to Railway PostgreSQL

### Session 3 — Three Fixes (2026-02-16)
**Fix 1: CallerIds Validation (P0)**
- `send_caller_id_selection_prompt()` now validates CallerIds against `get_retell_phone_number_set()` at display time
- Added `sync_caller_ids_with_retell()` utility + Celery periodic task `sync_caller_ids_task`
- Invalid CallerIds (not in Retell account) are hidden from users

**Fix 2: Agent Binding on Purchase (P1)**
- `handle_buynum_pay_wallet()` now calls `update_phone_number_agent()` after Retell purchase
- Binds user's first pathway as outbound agent
- Added "Bind Agent" button in "My Numbers" management
- New handlers: `handle_bind_agent_prompt()`, `handle_set_bind_agent()` for inbound/outbound agent selection

**Fix 3: Crypto Auto-Purchase (P1)**
- New model: `PendingPhoneNumberPurchase` (migration 0031)
- `make_payment()` saves purchase intent to DB before creating DynoPay crypto payment
- `crypto_transaction_webhook()` calls `_fulfill_pending_phone_purchase()` after wallet credit
- Auto-flow: crypto confirms → wallet credited → pending purchase detected → wallet debited → Retell purchase → agent bound → user notified

**Bonus: handle_caller_id parsing fix**
- Changed `call.data.split("_")[1]` to `call.data.replace("callerid_", "", 1)` for robustness

## Testing
- 12/12 backend tests passed (100%)
- All models, functions, endpoints verified

## Prioritized Backlog
### P0 - Critical
- [x] CallerIds validation against Retell
- [x] Agent binding after phone number purchase
- [x] Crypto auto-purchase flow

### P1 - Important
- [ ] Set Telegram webhook to pod URL (via Bot API setWebhook)
- [ ] Start Celery worker + beat for background tasks
- [ ] Create Django admin superuser

### P2 - Nice to Have
- [ ] Web dashboard for admin monitoring
- [ ] Automated CallerIds sync scheduling via Celery Beat
- [ ] Production deployment configuration
