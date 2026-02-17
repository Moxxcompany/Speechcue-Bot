# Speechcue Telegram Bot - PRD

## Original Problem Statement
1. Setup the Speechcue Telegram bot application with all environment variables and webhook
2. Add call outcome tracking — after each call, auto-send summary (duration, keypress responses, recording link)
3. Recording should be off by default, opt-in per call at $0.02 fee
4. Recordings served through our own URL (not Retell's)
5. Batch calls: threshold-based delivery (<5 individual, >=5 consolidated)

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn)
- **Telegram Bot**: pyTelegramBotAPI (webhook mode)
- **Voice AI**: Retell AI SDK
- **Payments**: DynoPay (crypto) + Internal Wallet (PostgreSQL)
- **Database**: PostgreSQL on Railway (nozomi.proxy.rlwy.net:19535)
- **Cache/Broker**: Redis on Railway (metro.proxy.rlwy.net:40681)
- **Task Queue**: Celery + Celery Beat (with django-celery-beat scheduler)

## User Personas
- **Bot Admin**: Manages IVR flows, campaigns, phone numbers
- **End User**: Uses Telegram bot to create call scripts and make calls

## Core Requirements (Static)
- IVR call script creation and management via Telegram bot
- Single and bulk voice calls via Retell AI
- DTMF input collection with supervisor approval flow
- Subscription plans (Free, Starter, Pro, Business)
- Internal wallet system with crypto top-up (DynoPay)
- Phone number purchasing and management (Retell)
- SMS inbox, call recordings, call history
- Multi-language support (English, Hindi, Chinese, French)
- Campaign scheduling and management

## What's Been Implemented

### Session 1 — Feb 17, 2026: Setup
- Created `/app/.env` and `/app/backend/.env` with all credentials
- Configured webhook_url to current pod: `https://quickstart-43.preview.emergentagent.com`
- Installed all Python dependencies, ran migrations
- Set Telegram webhook via API, verified all services running

### Session 2 — Feb 17, 2026: Call Outcome Tracking & Recording
**New files created:**
- `bot/recording_utils.py` — Token generation, verification, download, URL builders, formatting utils
- `bot/migrations/0034_*` — Model migrations for recording fields
- `payment/migrations/0051_*` — TransactionType RECORDING choice

**Models changed:**
- `CallLogsTable` — Added `recording_requested` (bool), `recording_fee` (decimal)
- `BatchCallLogs` — Added `recording_requested` (bool)
- `CallRecording` — NEW model: stores call_id, user_id, batch_id, retell_url, file_path, token, downloaded
- `TransactionType` — Added `RECORDING = "REC"` choice

**Call outcome summary (webhooks.py):**
- `_send_call_outcome_summary()` — Replaces `_deliver_recording_to_user()`, sends: duration, keypresses, disconnection reason, recording link (if opted in)
- `_handle_batch_call_summary()` — Threshold-based: <5 calls → individual, >=5 → consolidated
- `_send_batch_consolidated_summary()` — Sends one summary with stats + batch recordings page link

**Recording proxy (views.py):**
- `GET /api/recordings/<token>/` — Downloads from Retell on first access, caches locally, serves audio
- `GET /api/recordings/batch/<token>/` — HTML page listing all batch recordings with audio player

**Call flow updates (telegrambot.py):**
- Recording toggle button in call confirmation: `⚪ Recording: OFF (tap to enable $0.02)` / `🔴 Recording: ON ($0.02)`
- Wallet balance check before enabling recording
- $0.02 deducted from wallet per call on confirmation
- Batch recording: total fee = $0.02 × N calls, charged on batch start

**Async recording download (tasks.py):**
- `download_and_cache_recording` Celery task — downloads from Retell URL, saves to `/app/media/recordings/`

## Webhook Endpoints
| Endpoint | URL Path | Status |
|---|---|---|
| Telegram | `/api/telegram/webhook/` | Active |
| Retell AI | `/api/webhook/retell` | Active |
| DTMF Supervisor | `/api/dtmf/supervisor-check` | Active |
| SMS Inbound | `/api/webhook/sms` | Active |
| Time Check | `/api/time-check` | Active |
| Recording Proxy | `/api/recordings/<token>/` | NEW |
| Batch Recordings | `/api/recordings/batch/<token>/` | NEW |

## Prioritized Backlog
- P1: Configure Retell webhook URL in Retell dashboard to point to `/api/recordings/`
- P1: End-to-end test with real Retell call to verify recording download + Telegram delivery
- P2: Add recording playback directly in Telegram (send audio file instead of link)
- P2: Recording retention policy (auto-delete after 30 days)
- P2: Update TERMS_AND_CONDITIONS_URL and CHANNEL_LINK to actual values
- P3: Analytics dashboard for recording usage and fees collected
