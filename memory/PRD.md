# Speechcad IVR Telegram Bot - PRD

## Original Problem Statement
1. Analyze and setup the existing Django codebase
2. Analyze Bland.ai → Retell AI migration
3. Full bot flow documentation with Retell mapping
4. Configure Telegram bot webhook
5. Remove DynoPay wallet, build internal wallet, keep DynoPay for crypto payments

## Architecture
- **Framework**: Django 4.2.13 (ASGI/uvicorn on port 8001)
- **Database**: PostgreSQL 15 (tele_bot)
- **Cache/Broker**: Redis
- **Telegram Bot**: @Speechcuebot via webhook
- **Wallet**: Internal PostgreSQL (credit/debit/refund with atomic transactions)
- **Crypto Payments**: DynoPay API (master wallet token, no per-user tokens)
- **Voice API**: Bland.ai (pending Retell AI migration)

## What's Been Implemented
- [x] Full codebase setup
- [x] Bot token + webhook configured and verified
- [x] Email/phone onboarding steps removed
- [x] Internal wallet system (credit, debit, refund)
- [x] DynoPay crypto payment integration (master wallet token approach)
- [x] DynoPay API verified working (200 OK, QR code, transaction_id)
- [x] Retell AI migration analysis docs

## DynoPay Integration (Correct Pattern from HostingBotNew)
- **Base URL**: https://api.dynopay.com/api
- **Auth**: `x-api-key` + `Authorization: Bearer {DYNOPAY_WALLET_TOKEN}`
- **No per-user tokens** — single master wallet token for all payments
- **Endpoint**: `POST /user/cryptoPayment` → returns address + QR code
- **Webhook**: DynoPay calls our webhook → we `credit_wallet()` to internal balance
- **Currencies**: BTC, ETH, LTC, DOGE, USDT-TRC20, USDT-ERC20

## Prioritized Backlog
### P0 - Retell AI Migration
### P1 - Celery worker setup for background tasks
### P2 - Admin dashboard, transaction history in bot UI
