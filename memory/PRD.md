# Speechcue — PRD & Project Memory

## Original Problem Statement
Django Telegram Bot for IVR call management via Retell AI, crypto payments via DynoPay, user subscriptions.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: PostgreSQL 17.7 on Railway
- **Bot**: pyTelegramBotAPI — @Speechcuebot
- **Voice AI**: Retell AI SDK
- **Task Queue**: Celery + Redis (Railway)
- **Payments**: DynoPay crypto + internal wallet
- **Frontend**: React 19 (styled-components, react-router-dom v5)

## What's Been Implemented

### Session 4 — Setup, Button Fixes, Admin Shared Numbers, UX Rewrite (Jan 2026)

**Environment Setup:**
- Installed all Python/Node dependencies, configured real API credentials
- Set Telegram webhook to pod URL, PostgreSQL connected

**Bot Button Fixes (3 critical issues):**
1. Missing `answer_callback_query` in 90/95 handlers — auto-answer in webhook
2. Empty message crashes in Scheduled/Active Campaigns — added empty-state handling
3. Silent exception swallowing — added global BotExceptionHandler

**Admin Shared Phone Numbers:**
- Added `is_admin` and `telegram_username` fields to TelegramUser model
- `@onarrival1` (user_id=5590563715) auto-flagged as admin on every interaction
- Admin's phone numbers appear as "Shared" caller IDs for all users
- Education tip nudges users toward buying private numbers
- Username + chat_id captured/synced on every webhook interaction

**Complete UX Text Rewrite (100+ changes across 4 languages):**

| Before (Jargon) | After (User-Friendly) |
|---|---|
| IVR Flow | Call Script |
| Pathway | Call Script |
| Node | Step |
| Edge | Connection |
| DTMF / DTMF Input | Keypress / Keypress Responses |
| Bulk IVR Call | Batch Calls |
| Single IVR Call | Quick Call |
| Source Node / Target Node | From Step / To Step |
| Start Node | First Step |
| Feedback Node | Feedback Step |
| E.164 format | "with country code, e.g., +1..." |
| "Add Another Node" | "Add Another Step" |
| "Done Adding Edges" | "Done Connecting Steps" |
| "Select target node" | "Select the next step" |
| "Edges list is empty" | "No connections set up yet" |
| "Flow deleted successfully" | "Call script deleted!" |
| "No blocks" | "No steps yet" |
| /support | "Tap Help anytime!" |

**How It Works guide** fully rewritten in plain language (4 languages)
**Quick Start** updated to match new terminology
**All node type labels** updated (Get DTMF Input → Collect Keypress, etc.)

## Test Results
- Button Audit: 47/47 handlers passing via webhook E2E tests
- All syntax checks pass (translations.py, telegrambot.py, keyboard_menus.py)

## Backlog
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Call analytics web dashboard
- [ ] Multi-language voice selection in onboarding
