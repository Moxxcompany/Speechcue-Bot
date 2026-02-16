# Speechcad - PRD & Project Memory

## Original Problem Statement
1. Analyze and setup the existing Django Telegram Bot codebase
2. Update .env with real credentials (Telegram, Retell, PostgreSQL, Redis, DynoPay)
3. Analyze Retell caller ID, phone number purchasing, call forwarding, subscription payments
4. Implement fixes: CallerIds validation, agent binding on purchase, crypto auto-purchase
5. Implement: Real-time DTMF supervisor control, SMS inbox, recording delivery, voicemail/forwarding

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: PostgreSQL on Railway (`nozomi.proxy.rlwy.net:19535/railway`)
- **Bot**: pyTelegramBotAPI (Telegram Bot)
- **Voice AI**: Retell AI SDK
- **Task Queue**: Celery + Redis (Railway Redis)
- **Payments**: DynoPay crypto + internal wallet system

## Pod URL
`https://f723c344-fa07-4ea8-924c-2345ee24681e.preview.emergentagent.com`

## Webhook URLs (for Retell Dashboard)
- **Retell Voice**: `.../api/webhook/retell`
- **Supervisor DTMF Check**: `.../api/dtmf/supervisor-check`
- **Inbound SMS**: `.../api/webhook/sms`
- **Telegram**: `.../api/telegram/webhook/`
- **Crypto Deposit**: `.../webhook/crypto_deposit`
- **Crypto Transaction**: `.../webhook/crypto_transaction`

## What's Been Implemented

### Session 1 — Setup (2026-02-16)
- Installed all Python dependencies, created .env, ran migrations
- Backend running via supervisor

### Session 2 — Env + PostgreSQL (2026-02-16)
- Real keys configured, PostgreSQL via POSTGRES_URL, all migrations applied

### Session 3 — Three Fixes (2026-02-16)
- CallerIds validation against Retell phone numbers (P0)
- Agent binding after phone number purchase (P1)
- Crypto auto-purchase flow with PendingPhoneNumberPurchase model (P1)

### Session 4 — DTMF Supervisor + SMS + Voicemail/Forwarding (2026-02-16)

**Real-Time DTMF Streaming**
- `_handle_transcript_updated()` in webhooks.py — parses live transcript for "Pressed Button: X"
- Sends instant Telegram notification to bot user (~1.5s latency)
- Skips bulk campaign calls (single calls only)
- Cursor tracking (`_transcript_cursor`) avoids duplicate messages

**Supervisor DTMF Approval (Option B)**
- `PendingDTMFApproval` model — tracks call_id, digits, status (pending/approved/rejected/timeout)
- `dtmf_supervisor_check` endpoint at `/api/dtmf/supervisor-check`
  - Called by Retell custom function mid-call
  - Creates approval record, sends Telegram inline keyboard [Approve/Reject]
  - Polls DB every 2s for up to 20s, returns proceed/re_enter to Retell
  - Auto-approves on timeout
  - Skips bulk campaign calls
- Bot handlers: `handle_dtmf_approve`, `handle_dtmf_reject`
- `register_supervisor_function_on_agent()` — auto-registers custom function on Retell agent

**DTMF Node Builder Enhancement**
- `handle_dtmf_input_node()` enhanced with:
  - Self-validation prompt ("You entered X. Press 1 to confirm, star to re-enter")
  - Loop-back edge on invalid/rejected input
  - Auto-registers supervisor custom function on agent

**SMS Inbox**
- `SMSInbox` model — stores from_number, to_number, message, read status
- `inbound_sms_webhook` at `/api/webhook/sms` — receives SMS, matches to user's number, delivers via Telegram
- Bot handlers: `handle_sms_inbox`, `handle_sms_view`, `handle_sms_clear_read`
- SMS Inbox button in "My Numbers" with unread count badge

**Recording Delivery**
- `_deliver_recording_to_user()` — sends recording_url to bot user after call ends
- Detects inbound vs outbound calls, formats message accordingly
- Called automatically from `_handle_call_ended()`

**Voicemail Settings**
- `voicemail_enabled`, `voicemail_message` fields on UserPhoneNumber
- Bot handlers: `handle_voicemail_toggle`, `handle_voicemail_edit`
- Accessible via "My Numbers" → "Settings" → "Voicemail"

**Call Forwarding Settings**
- `forwarding_enabled`, `forwarding_number` fields on UserPhoneNumber
- Bot handlers: `handle_forwarding_toggle`, `handle_forwarding_set`
- E.164 format validation
- Accessible via "My Numbers" → "Settings" → "Forwarding"

## Testing
- Session 3: 12/12 tests passed (100%)
- Session 4: 17/18 tests passed (94.4%) — 1 minor proxy issue, not code

## Models Added
- `PendingDTMFApproval` (migration 0032)
- `SMSInbox` (migration 0032)
- `PendingPhoneNumberPurchase` (migration 0031)
- Fields on `UserPhoneNumber`: voicemail_enabled, voicemail_message, forwarding_enabled, forwarding_number

## Prioritized Backlog
### P0 - Done
- [x] CallerIds validation
- [x] Agent binding on purchase
- [x] Crypto auto-purchase
- [x] Real-time DTMF streaming
- [x] Supervisor DTMF approval (single calls)
- [x] SMS Inbox
- [x] Recording delivery
- [x] Voicemail toggle
- [x] Call forwarding settings
- [x] DTMF node loop-back/confirmation

### P1 - Remaining
- [ ] Inbound call billing (charge wallet for inbound minutes)
- [ ] After-hours conditional routing (business hours)
- [ ] Retell agent prompt auto-update for voicemail/forwarding settings
- [ ] Set Telegram webhook to pod URL
- [ ] Start Celery worker + beat

### P2 - Deferred
- [ ] Outbound SMS (requires A2P 10DLC registration)
- [ ] Web admin dashboard
