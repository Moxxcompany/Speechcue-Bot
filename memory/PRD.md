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

## Session 4 — Full UX Audit & Fixes (Jan 2026)

### Bugs Found & Fixed
1. **`display_create_ivr_flows_ai` was EMPTY** — "AI-Powered Script" button from main menu did nothing. Fixed: now calls `initiate_ai_assisted_flow()`
2. **`user_id[lg]` crash** in `handle_call_back_view_task` (line 6194) — trying to subscript an integer with language string. Fixed: changed to `user_id`
3. **`ai_assisted_user_flow_keyboard` passed as reference** not called — Fixed: added `(user_id)` call
4. **Missing `answer_callback_query`** on 90/95 handlers — auto-answer in webhook
5. **Empty message crashes** in Scheduled/Active Campaigns — added empty-state handling

### Friction Points Identified & Fixed

**Onboarding Flow:**
- Terms URL was hardcoded to a generic template site — still needs real T&C URL
- After accepting terms, "Quick Start" guide exists but referenced /support which doesn't exist → Fixed to "Tap Help anytime!"

**Jargon Elimination (100+ changes, 4 languages):**
| Before | After |
|---|---|
| IVR Flow / Pathway | Call Script |
| Node | Step |
| Edge | Connection |
| DTMF / DTMF Input | Keypress / Keypress Responses |
| Bulk IVR Call | Batch Calls |
| Single IVR Call | Quick Call |
| Source/Target Node | From Step / To Step |
| Start Node | First Step |
| E.164 format | "with country code, e.g., +1..." |
| Feedback Node | Feedback Step |
| "Add Another Node" | "Add Another Step" |
| "Done Adding Edges" | "Done Connecting Steps" |
| "Overage auto-deducts" | "Extra usage auto-deducts" |
| "Minimum wallet balance for 2 minutes" | "You need at least $0.70 in your wallet" |

**Call Flow UX:**
- Pay-as-you-go pricing message cleaned up — removed "(wallet deduction)" jargon
- "Intl calls" → "International calls"
- Subscription status messages simplified

### Remaining Friction Points (Backlog)
- Terms URL still points to generic template — needs real URL
- No inline "cancel" during multi-step flows (script creation, number purchase)
- Campaign scheduling has no timezone awareness hint for users
- "Bind Agent" button in My Numbers uses technical language

## Test Results
- Button Audit: 47/47 handlers passing via webhook E2E tests
- All syntax checks pass

## Backlog
- [ ] Real Terms & Conditions URL
- [ ] Cancel/back buttons in multi-step flows
- [ ] Timezone hint in campaign scheduling
- [ ] "Bind Agent" → "Set Inbound Script" rename
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Call analytics web dashboard
