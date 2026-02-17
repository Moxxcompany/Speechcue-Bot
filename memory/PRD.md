# Speechcad (Speechcue) — PRD & Project Memory

## Original Problem Statement
Django Telegram Bot for IVR call management via Retell AI, crypto payments via DynoPay, user subscriptions. Tasks: setup, real credentials, inbound billing, Retell agent auto-update, Celery, after-hours routing, and full UI/UX redesign.

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn on port 8001)
- **Database**: PostgreSQL 17.7 on Railway (connected)
- **Bot**: pyTelegramBotAPI — @Speechcuebot
- **Voice AI**: Retell AI SDK
- **Task Queue**: Celery + Redis (Railway)
- **Payments**: DynoPay crypto + internal wallet
- **Frontend**: React 19 (styled-components, react-router-dom v5)

## What's Been Implemented

### Session 1-3 — (Previous)
- Full IVR bot with voice AI, crypto payments, billing, campaigns
- UI/UX redesign with 8-button main menu, hub-style navigation
- Real-time overage billing
- 34 translation strings in 4 languages

### Session 4 — Setup & Bug Fixes (Jan 2026)

**Environment Setup:**
- Installed all Python dependencies (Django, Celery, Retell SDK, etc.)
- Installed missing frontend npm packages (react-router-dom@5, styled-components, history@4)
- Created `.env` files with real API credentials (Telegram, Retell, DynoPay, Redis, PostgreSQL)
- Set Telegram webhook to current pod URL
- Both backend and frontend running successfully

**Bot Button Fixes — 3 critical issues found and fixed:**

1. **Missing `answer_callback_query`** (90/95 inline button handlers):
   - All inline buttons appeared "unresponsive" (spinning loader for 30s) because handlers didn't acknowledge the button press
   - **Fix**: Added auto-answer in `telegram_webhook.py` — calls `answer_callback_query` before processing every callback update

2. **Empty message crashes** (2 handlers):
   - `Scheduled Campaigns` and `Active Campaigns` buttons crashed with "Bad Request: message text is empty" when user had no campaigns
   - **Fix**: Added empty-state handling with "No campaigns yet" messages and back navigation

3. **Silent exception swallowing**:
   - Bot handler exceptions were silently ignored, making debugging impossible
   - **Fix**: Added global `BotExceptionHandler` that logs all handler crashes

**Audit Results:** 47/47 button handlers tested and passing via webhook E2E tests

## Test Results
- Iterations 3-6: All passed (previous sessions)
- Button Audit: 47/47 handlers passing (current session)

## Current Status
- Backend: RUNNING (Django ASGI, PostgreSQL connected, Retell initialized)
- Frontend: RUNNING (React dev server)
- Webhook: Active at current pod URL
- All 47 tested bot buttons: WORKING

## Backlog
- [ ] Outbound SMS (requires A2P 10DLC)
- [ ] Call analytics dashboard
- [ ] Multi-language voice selection in onboarding
