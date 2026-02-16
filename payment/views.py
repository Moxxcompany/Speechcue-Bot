"""
Hybrid Wallet System:
  - Internal PostgreSQL wallet for balance management (credit, debit, refund)
  - DynoPay for crypto payment generation (address, QR code) and user registration
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

# DynoPay config — used ONLY for crypto payment generation
x_api_key = os.getenv("x-api-key")
dynopay_base_url = os.getenv("dynopay_base_url")


# =============================================================================
# DynoPay: User registration (needed for crypto payment auth token)
# =============================================================================

def setup_user(user_id, email, mobile, name, username):
    """
    1. Create/update TelegramUser locally with $0 wallet balance.
    2. Register with DynoPay to get token + customer_id (for crypto payments).
    """
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

        # Register with DynoPay for crypto payment capabilities
        if not user.token:
            try:
                url = f"{dynopay_base_url}/user/createUser"
                payload = json.dumps({"email": email, "name": name, "mobile": mobile})
                headers = {"x-api-key": x_api_key, "Content-Type": "application/json"}
                response = requests.post(url, headers=headers, data=payload)

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    token = data.get("token")
                    customer_id = data.get("customer_id")
                    if token and customer_id:
                        user.token = token
                        user.customer_id = customer_id
                        user.save(update_fields=["token", "customer_id"])
                        logger.info(f"DynoPay user created for {user_id}")
                    else:
                        logger.warning(f"DynoPay response missing token/customer_id for {user_id}")
                else:
                    logger.warning(f"DynoPay createUser failed ({response.status_code}): {response.text}")
            except RequestException as e:
                logger.warning(f"DynoPay createUser network error for {user_id}: {e}")
                # Non-fatal — user can still use wallet, just can't do crypto top-ups yet

        return {"status": 200, "text": "User setup complete"}
    except Exception as e:
        logger.error(f"setup_user error: {e}")
        return {"status": 500, "text": str(e)}


# =============================================================================
# Internal Wallet: Balance management (no DynoPay)
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
# DynoPay: Crypto payment generation (address + QR code)
# =============================================================================

def create_crypto_payment(user_id, amount, currency, redirect_uri, auto_renewal, top_up=False):
    """
    Call DynoPay API to generate a crypto payment address + QR code.
    On payment confirmation (via DynoPay webhook), we credit the internal wallet.
    """
    url = f"{dynopay_base_url}/user/cryptoPayment"
    token = TelegramUser.objects.get(user_id=user_id).token

    if not token:
        class ErrorResponse:
            status_code = 400
            text = "No DynoPay token — user needs to re-register for crypto payments"
            def json(self):
                return {"message": self.text}
        return ErrorResponse()

    payload = json.dumps({
        "amount": float(amount),
        "currency": currency,
        "redirect_uri": redirect_uri,
        "topUp": top_up,
        "meta_data": {
            "product_name": f"{user_id}",
            "product": f"{auto_renewal}",
        },
    })
    headers = {
        "x-api-key": x_api_key,
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    response = requests.post(url, headers=headers, data=payload)
    logger.info(f"create_crypto_payment for user {user_id}: {response.status_code}")
    return response


# =============================================================================
# Backward-compatible aliases (used by telegrambot.py & tasks.py)
# =============================================================================

def credit_wallet_balance(user_id, amount):
    """
    Backward-compatible wrapper: deducts from internal wallet.
    (DynoPay's 'useWallet' was a debit — name is confusing but kept for compat.)
    Returns a response-like object.
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
# Transaction queries (local DB — no DynoPay)
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
