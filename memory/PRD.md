# Speechcad (Speechcue) — PRD & Project Memory

## Original Problem Statement
Django Telegram Bot for IVR call management via Retell AI, crypto payments via DynoPay, user subscriptions. Tasks: setup, real credentials, inbound billing, Retell agent auto-update, Celery, after-hours routing, and full UI/UX redesign.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: SQLite (local dev) / PostgreSQL 17.7 on Railway (production)
- **Bot**: pyTelegramBotAPI — @Speechcuebot
- **Voice AI**: Retell AI SDK
- **Task Queue**: Celery + Redis (Railway) — auto-starts with backend
- **Payments**: DynoPay crypto + internal wallet
- **Frontend**: React 19 (styled-components, react-router-dom v5)

## What's Been Implemented

### Session 1 — Setup & Credentials
- Installed all Python dependencies, ran PostgreSQL migrations
- Configured real API keys (Telegram, Retell, DynoPay, Redis, PostgreSQL)
- Set Telegram webhook to pod URL
- Celery worker + beat auto-start via server.py

### Session 2 — Real-Time Billing
- Moved overage charging from 5-min Celery poll to immediate webhook billing
- `_charge_overage_realtime()` fires on call_ended for both batch and free plan calls
- Celery task demoted to hourly safety-net

### Session 3 — Full UI/UX Redesign
**Redesigned Main Menu** (8 buttons, 4 rows):
- Phone Numbers | IVR Flows
- Make a Call | Campaigns
- Inbox | Wallet & Billing
- Account | Help

**New Features:**
1. **Phone Numbers Hub** — Buy Number, My Numbers (with count), SMS Inbox (with unread count)
2. **Inbox Hub** — Call Recordings (fetch from Retell), DTMF Responses (by flow), SMS Messages, Call History (last 10 calls with duration/status)
3. **Wallet & Billing Hub** — Balance display, Top Up, Transaction History (last 15 txs), View/Upgrade Subscription
4. **Dashboard Summary** — Returning users see plan/wallet/numbers/minutes at a glance
5. **Onboarding Fix** — After T&C: Quick Start guide, Free Plan / Premium Plans / How It Works (no forced plan selection)
6. **34 new translation strings** in 4 languages (EN/ZH/FR/HI)

### Session 4 — Environment Setup (Current - Jan 2026)
**Fixed setup issues:**
- Installed all Python dependencies from requirements.txt (Django, Celery, Retell SDK, etc.)
- Installed missing frontend npm packages (react-router-dom@5, styled-components, history@4)
- Installed ESLint config (airbnb + plugins)
- Fixed bot_config.py to handle missing API_TOKEN gracefully
- Fixed React 19 deprecated ReactDOM.render → createRoot
- Fixed ESLint blank line errors in routes/index.js
- Created /app/.env for Django settings
- Created /app/frontend/.env with REACT_APP_BACKEND_URL
- Ran Django migrations (SQLite fallback — no PostgreSQL creds configured)
- Both backend and frontend running successfully

## Test Results
- Iteration 3: 9/9 passed (setup)
- Iteration 4: 14/14 passed (real-time billing)
- Iteration 5: 12/12 passed (UI/UX structure)
- Iteration 6: 16/16 passed (final validation)

## All Tasks Status
| Task | Status |
|------|--------|
| Setup + real credentials | ✅ |
| Inbound call billing | ✅ |
| Retell agent auto-update | ✅ |
| Telegram webhook + Celery | ✅ |
| After-hours routing | ✅ |
| Real-time overage billing | ✅ |
| Phone Numbers hub | ✅ |
| Onboarding fix | ✅ |
| Inbox consolidation | ✅ |
| Wallet & Transaction History | ✅ |
| Dashboard summary | ✅ |
| Environment setup (local dev) | ✅ |

## Current Environment Status
- Backend: RUNNING (Django ASGI via uvicorn on port 8001)
- Frontend: RUNNING (React dev server on port 3000)
- Database: SQLite (local) — needs POSTGRES_URL env var for Railway PostgreSQL
- Bot: Needs real API_TOKEN in /app/.env for Telegram functionality
- Celery: Needs REDIS_URL in /app/.env for task queue
- Retell AI: Needs RETELL_API_KEY in /app/.env for voice features

## Missing Credentials (for full functionality)
- `API_TOKEN` — Telegram Bot token
- `POSTGRES_URL` — Railway PostgreSQL connection string
- `REDIS_URL` — Redis connection string for Celery
- `RETELL_API_KEY` — Retell AI API key
- `DYNOPAY_API_KEY` — DynoPay crypto payment key

## Backlog
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Call analytics dashboard
- [ ] Multi-language voice selection in onboarding
