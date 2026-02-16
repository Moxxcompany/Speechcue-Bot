"""
Hybrid Wallet System:
  - Internal PostgreSQL wallet for balance management (credit, debit, refund)
  - DynoPay for crypto payment generation (address, QR code) via single wallet token
  - On crypto payment confirmation (webhook), funds are credited to internal wallet
"""
import json
import logging
import os
from decimal import Decimal

import requests
from django.db import transaction
from requests.exceptions import RequestException

from user.models import TelegramUser
from payment.models import WalletTransaction, TransactionType, UserTransactionLogs

logger = logging.getLogger(__name__)

# DynoPay config — single wallet token for all crypto payments
DYNOPAY_BASE_URL = os.getenv("DYNOPAY_BASE_URL", "https://api.dynopay.com/api")
DYNOPAY_API_KEY = os.getenv("DYNOPAY_API_KEY", "")
DYNOPAY_WALLET_TOKEN = os.getenv("DYNOPAY_WALLET_TOKEN", "")


# =============================================================================
# User Setup (no DynoPay user creation needed — uses master wallet token)
# =============================================================================

def setup_user(user_id, email, mobile, name, username):
    """Create or get a TelegramUser with $0 wallet balance. No external API needed."""
    try:
        user, created = TelegramUser.objects.get_or_create(
            user_id=user_id,
            defaults={
                "user_name": username,
                "language": "English",
                "subscription_status": "inactive",
                "free_plan": True,
                "wallet_balance": Decimal("0.00"),
            },
        )
        if not created:
            user.user_name = username
            user.save(update_fields=["user_name"])

        return {"status": 200, "text": "User setup complete"}
    except Exception as e:
        logger.error(f"setup_user error: {e}")
        return {"status": 500, "text": str(e)}


# =============================================================================
# Internal Wallet: Balance management
# =============================================================================

def check_user_balance(user_id):
    """Read wallet balance from local DB."""
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        return {
            "status": 200,
            "data": {"amount": str(user.wallet_balance), "currency": "USD"},
        }
    except TelegramUser.DoesNotExist:
        return {"status": 404, "data": {"amount": "0.00", "currency": "USD"}}


def credit_wallet(user_id, amount, description="Deposit", reference=None, tx_type=TransactionType.DEPOSIT):
    """Add funds to internal wallet. Used for crypto top-up confirmations, refunds, admin credits."""
    amount = Decimal(str(amount))
    if amount <= 0:
        return {"status": 400, "message": "Amount must be positive"}

    try:
        with transaction.atomic():
            user = TelegramUser.objects.select_for_update().get(user_id=user_id)
            balance_before = user.wallet_balance
            user.wallet_balance += amount
            user.save(update_fields=["wallet_balance"])

            tx = WalletTransaction.objects.create(
                user=user,
                transaction_type=tx_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=user.wallet_balance,
                description=description,
                reference=reference,
            )
        return {
            "status": 200,
            "data": {
                "transaction_id": str(tx.transaction_id),
                "balance": str(user.wallet_balance),
            },
        }
    except TelegramUser.DoesNotExist:
        return {"status": 404, "message": "User not found"}
    except Exception as e:
        logger.error(f"credit_wallet error for user {user_id}: {e}")
        return {"status": 500, "message": str(e)}


def debit_wallet(user_id, amount, description="Charge", reference=None, tx_type=TransactionType.SUBSCRIPTION):
    """Deduct funds from internal wallet. Fails if insufficient balance."""
    amount = Decimal(str(amount))
    if amount <= 0:
        return {"status": 400, "message": "Amount must be positive"}

    try:
        with transaction.atomic():
            user = TelegramUser.objects.select_for_update().get(user_id=user_id)
            if user.wallet_balance < amount:
                return {"status": 402, "message": "Insufficient balance"}

            balance_before = user.wallet_balance
            user.wallet_balance -= amount
            user.save(update_fields=["wallet_balance"])

            tx = WalletTransaction.objects.create(
                user=user,
                transaction_type=tx_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=user.wallet_balance,
                description=description,
                reference=reference,
            )
        return {
            "status": 200,
            "data": {
                "transaction_id": str(tx.transaction_id),
                "balance": str(user.wallet_balance),
            },
        }
    except TelegramUser.DoesNotExist:
        return {"status": 404, "message": "User not found"}
    except Exception as e:
        logger.error(f"debit_wallet error for user {user_id}: {e}")
        return {"status": 500, "message": str(e)}


def refund_wallet(user_id, amount, description="Refund", reference=None):
    """Refund funds to wallet. Creates a REFUND transaction."""
    return credit_wallet(
        user_id, amount,
        description=description,
        reference=reference,
        tx_type=TransactionType.REFUND,
    )


# =============================================================================
# DynoPay: Crypto payment generation (using master wallet token)
# =============================================================================

def create_crypto_payment(user_id, amount, currency, redirect_uri, auto_renewal, top_up=False):
    """
    Call DynoPay API to generate a crypto payment address + QR code.
    Uses master wallet token (DYNOPAY_WALLET_TOKEN) — no per-user token needed.
    On payment confirmation (via DynoPay webhook), we credit the internal wallet.
    """
    if not DYNOPAY_API_KEY or not DYNOPAY_WALLET_TOKEN:
        logger.error("DynoPay credentials not configured")

        class ErrorResponse:
            status_code = 500
            text = "Payment system not configured. Please contact support."
            def json(self):
                return {"message": self.text}
        return ErrorResponse()

    # Map currency codes to DynoPay format
    currency_map = {
        "BTC": "BTC",
        "ETH": "ETH",
        "LTC": "LTC",
        "DOGE": "DOGE",
        "USDT_TRC20": "USDT-TRC20",
        "USDT_ERC20": "USDT-ERC20",
        "TRC-20 USDT": "USDT-TRC20",
        "ERC-20 USDT": "USDT-ERC20",
    }
    dynopay_currency = currency_map.get(currency.upper(), currency.upper())

    url = f"{DYNOPAY_BASE_URL}/user/cryptoPayment"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": DYNOPAY_API_KEY,
        "Authorization": f"Bearer {DYNOPAY_WALLET_TOKEN}",
    }

    payload = {
        "amount": float(amount),
        "currency": dynopay_currency,
        "webhook_url": redirect_uri,
        "product_id": f"crypto_{dynopay_currency.lower()}",
        "meta_data": {
            "product_name": str(user_id),
            "product": str(auto_renewal),
            "refId": f"speechcue_{user_id}",
            "user_id": str(user_id),
            "top_up": str(top_up),
        },
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        logger.info(f"DynoPay cryptoPayment for user {user_id}: {response.status_code}")
        return response
    except RequestException as e:
        logger.error(f"DynoPay cryptoPayment network error: {e}")

        class ErrorResponse:
            status_code = 503
            text = f"Payment service temporarily unavailable: {e}"
            def json(self):
                return {"message": self.text}
        return ErrorResponse()


# =============================================================================
# Backward-compatible aliases (used by telegrambot.py & tasks.py)
# =============================================================================

def credit_wallet_balance(user_id, amount):
    """
    Backward-compatible wrapper: deducts from internal wallet.
    (DynoPay's 'useWallet' was a debit — name is confusing but kept for compat.)
    """
    result = debit_wallet(user_id, amount, description="Payment deduction")

    class FakeResponse:
        def __init__(self, data):
            self._data = data
            self.status_code = data["status"]
            self.text = str(data)
        def json(self):
            return self._data

    return FakeResponse(result)


# =============================================================================
# Transaction queries (local DB)
# =============================================================================

def get_user_single_transaction(user_id, transaction_id):
    """Get a single transaction by ID from local DB."""
    try:
        tx = WalletTransaction.objects.get(transaction_id=transaction_id)
        return {
            "status": 200,
            "data": {
                "transaction_id": str(tx.transaction_id),
                "type": tx.get_transaction_type_display(),
                "amount": str(tx.amount),
                "balance_before": str(tx.balance_before),
                "balance_after": str(tx.balance_after),
                "description": tx.description,
                "created_at": str(tx.created_at),
            },
        }
    except WalletTransaction.DoesNotExist:
        return {"status": 404, "data": None}


def get_all_user_transactions(user_id, limit=50):
    """Get all transactions for a user from local DB."""
    txs = WalletTransaction.objects.filter(user_id=user_id)[:limit]
    return {
        "status": 200,
        "data": [
            {
                "transaction_id": str(tx.transaction_id),
                "type": tx.get_transaction_type_display(),
                "amount": str(tx.amount),
                "balance_before": str(tx.balance_before),
                "balance_after": str(tx.balance_after),
                "description": tx.description,
                "created_at": str(tx.created_at),
            }
            for tx in txs
        ],
    }
