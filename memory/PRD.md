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

### Session 4 — Full UX Overhaul (Jan 2026)

**Environment Setup:**
- All Python/Node deps installed, real API credentials configured
- Telegram webhook set to pod URL, PostgreSQL connected

**Bug Fixes:**
1. Missing `answer_callback_query` in 90/95 handlers — auto-answer in webhook
2. Empty message crashes in Scheduled/Active Campaigns
3. `display_create_ivr_flows_ai` was an empty function (no-op)
4. `user_id[lg]` crash in View AI Scripts
5. `ai_assisted_user_flow_keyboard` passed as reference not called

**Admin Shared Phone Numbers:**
- `is_admin` + `telegram_username` fields on TelegramUser
- `@onarrival1` auto-flagged as admin; numbers show as Shared caller IDs
- Education tip nudges private number purchase

**Complete UX Text Rewrite (100+ changes, 4 languages):**
- IVR Flow/Pathway → Call Script, Node → Step, Edge → Connection
- DTMF → Keypress, Bulk IVR → Batch Calls, Single IVR → Quick Call
- All prompts, guides, error messages rewritten in plain language

**Guided First-Call Wizard:**
- After activating free plan, users see "Try Your First Call" offer
- Enter phone number → Retell creates temp agent → AI calls user in 30 seconds
- Uses shared admin caller ID if available
- Skip option available; Cancel returns to main menu
- Success message directs to Call Scripts for next step

**Cancel/Back in Multi-Step Flows:**
- `/cancel` command handler clears any active step → main menu
- "Cancel" text button handler during any step flow
- `get_force_reply()` now shows Cancel button instead of bare ForceReply
- Works across: script creation, number purchase, phone input, name entry, campaign setup

**"Bind Agent" → "Set Inbound Script":**
- Button label: "Set Inbound Script" (was "Bind Agent")
- Prompt explains: "Choose a call script to handle incoming calls"
- Unbind label: "Remove inbound script" (was "Unbind")
- Confirmation messages use plain language

**Timezone Hint in Campaign Scheduling:**
- Replaced bare datetime prompt with rich timezone hint
- Shows format, example, and common cities list
- Users enter: `YYYY-MM-DD HH:mm City`

## Test Results
- Button Audit: 47/47 handlers passing
- Wizard callbacks: wizard_start, wizard_skip working
- /cancel command: working
- All syntax checks pass

## Backlog
- [ ] Real Terms & Conditions URL
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Call analytics web dashboard
- [ ] Multi-language voice selection in onboarding
