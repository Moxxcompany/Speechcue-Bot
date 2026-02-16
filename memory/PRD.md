# PRD - Telegram IVR Bot

## Problem Statement
Analyze and set up an existing Django-based Telegram Bot codebase for IVR (Interactive Voice Response) management.

## Architecture
- **Backend**: Django 4.2.13 (Python 3.11)
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis
- **Task Queue**: Celery + django-celery-beat, Huey
- **Bot Framework**: pyTelegramBotAPI
- **External APIs**: Bland.ai (IVR calls), DynoPay (crypto payments), Tatum (crypto rates)

## Core Features
- Telegram Bot for IVR call management (single/bulk)
- Multi-language support (English, Hindi, Chinese, French)
- Subscription plans with crypto payments (USDT)
- Campaign management with batch calls
- DTMF input handling
- AI-assisted task flows (pathways)
- Scheduled calls & reminders
- User wallet management
- Call logging & duration tracking

## Django Apps
- `bot` - Core bot logic, views, webhooks, call management
- `user` - Telegram user model
- `payment` - Subscriptions, transactions, wallets, DTMF inbox
- `translations` - Multi-language support

## What's Been Implemented (Setup - Jan 2026)
- Installed PostgreSQL 15, Redis, all Python dependencies
- Created `.env` with database config and placeholder API keys
- Ran all migrations (38 tables created)
- Seeded 10 subscription plans
- Fixed bot_config.py to gracefully handle missing Telegram API token
- Django server verified to start without errors

## API Keys Required (Placeholders)
- `API_TOKEN` - Telegram Bot token
- `BLAND_API_KEY` - Bland.ai API key for IVR calls
- `BLAND_WEBHOOK_SIGNING_SECRET` - Webhook verification
- `x-api-key` - DynoPay API key
- `webhook_url` - Bot webhook URL
- `dynopay_base_url` - DynoPay base URL

## Next Action Items
- User needs to provide real API keys (Telegram, Bland.ai, DynoPay)
- Start Celery worker and beat scheduler for periodic tasks
- Configure webhook URL for Telegram bot
- Run `python manage.py startbot` to start the bot polling

## Backlog
- P0: Configure real API keys and verify bot functionality
- P1: Set up Celery workers for async task processing
- P2: Configure webhook-based bot mode for production
