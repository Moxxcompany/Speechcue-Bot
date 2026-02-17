# Speechcue Telegram Bot - PRD

## Original Problem Statement
1. Setup the Speechcue Telegram bot application with all environment variables and webhook
2. Add call outcome tracking — after each call, auto-send summary (duration, keypress responses, recording link)
3. Recording should be off by default, opt-in per call at $0.02 fee
4. Recordings served through our own URL (not Retell's)
5. Batch calls: threshold-based delivery (<5 individual, >=5 consolidated)
6. Inline audio playback in Telegram — send audio files directly in chat

## Architecture
- **Framework**: Django 4.2.13 (ASGI via uvicorn)
- **Telegram Bot**: pyTelegramBotAPI (webhook mode)
- **Voice AI**: Retell AI SDK
- **Payments**: DynoPay (crypto) + Internal Wallet (PostgreSQL)
- **Database**: PostgreSQL on Railway (nozomi.proxy.rlwy.net:19535)
- **Cache/Broker**: Redis on Railway (metro.proxy.rlwy.net:40681)
- **Task Queue**: Celery + Celery Beat (django-celery-beat scheduler)

## User Personas
- **Bot Admin**: Manages IVR flows, campaigns, phone numbers
- **End User**: Uses Telegram bot to create call scripts and make calls

## What's Been Implemented

### Session 1 — Feb 17, 2026: Initial Setup
- Environment variables configured, webhook set, all services running

### Session 2 — Feb 17, 2026: Call Outcome Tracking & Per-Call Recording
- `_send_call_outcome_summary()`: Auto-sends duration, keypresses, disconnection reason after every call
- Recording toggle in call confirmation: `⚪ Recording: OFF (tap to enable $0.02)` / `🔴 Recording: ON ($0.02)`
- $0.02/call fee deducted from wallet; `TransactionType.RECORDING = "REC"` added
- `CallRecording` model: stores call_id, user_id, batch_id, retell_url, file_path, token
- Recording proxy: `GET /api/recordings/<token>/` downloads from Retell on first access, caches locally
- Batch recordings page: `GET /api/recordings/batch/<token>/` renders HTML with audio players
- Threshold delivery: <5 calls individual summaries, >=5 one consolidated summary
- Celery task `download_and_cache_recording` for async download

### Session 3 — Feb 17, 2026: Inline Audio Playback
- `_send_recording_inline()`: After Celery downloads recording, sends audio file via `bot.send_audio()` directly in Telegram chat
- `_send_recording_fallback()`: Falls back to recording URL link if inline audio fails
- Single calls: Summary message says "Recording incoming...", then audio file arrives async
- Small batches (<5): Individual audio files sent per call as they complete
- Large batches (>=5): All audio files sent together after consolidated summary message
- Inbox "Play Recording" button: Sends cached audio inline if available, otherwise downloads from Retell and sends
- HTTP proxy endpoint kept as fallback for web-based access

## Files Modified/Created
| File | Action | Description |
|---|---|---|
| `bot/models.py` | Modified | Added recording_requested, recording_fee to CallLogsTable/BatchCallLogs; Created CallRecording model |
| `bot/recording_utils.py` | Created | Token generation, verification, download, URL builders |
| `bot/webhooks.py` | Modified | _send_call_outcome_summary, _handle_batch_call_summary, _send_batch_consolidated_summary |
| `bot/tasks.py` | Modified | download_and_cache_recording + _send_recording_inline + _send_recording_fallback |
| `bot/views.py` | Modified | serve_recording proxy, batch_recordings_page HTML |
| `bot/telegrambot.py` | Modified | Recording toggle, inline audio in play_recording, batch flow |
| `TelegramBot/urls.py` | Modified | Added /api/recordings/ routes |
| `payment/models.py` | Modified | Added RECORDING transaction type |

## Prioritized Backlog
- P1: Configure Retell dashboard webhook URL to point to our endpoint
- P1: End-to-end test with real Retell call
- P2: Recording retention policy (auto-delete after 30 days)
- P2: Update placeholder URLs (terms, channel link)
- P3: Analytics dashboard for recording usage stats
