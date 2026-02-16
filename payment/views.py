"""
Internal Wallet System — replaces DynoPay external API.
All wallet operations are local PostgreSQL transactions.
"""
import logging
from decimal import Decimal

from django.db import transaction

from user.models import TelegramUser
from payment.models import WalletTransaction, TransactionType, UserTransactionLogs

logger = logging.getLogger(__name__)


def setup_user(user_id, email, mobile, name, username):
    """
    Create or get a TelegramUser with an internal wallet (balance starts at 0).
    No external API call needed — purely local.
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

        return {"status": 200, "text": "User setup complete"}
    except Exception as e:
        logger.error(f"setup_user error: {e}")
        return {"status": 500, "text": str(e)}


def check_user_balance(user_id):
    """
    Get wallet balance from local DB.
    Returns dict mimicking the old DynoPay response shape for compatibility.
    """
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        return {
            "status": 200,
            "data": {
                "amount": str(user.wallet_balance),
                "currency": "USD",
            },
        }
    except TelegramUser.DoesNotExist:
        return {"status": 404, "data": {"amount": "0.00", "currency": "USD"}}


def credit_wallet(user_id, amount, description="Deposit", reference=None, tx_type=TransactionType.DEPOSIT):
    """
    Add funds to wallet. Used for top-ups and refunds.
    Returns dict with status and new balance.
    """
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
    """
    Deduct funds from wallet. Used for subscriptions, overage charges, etc.
    Returns dict with status. Fails if insufficient balance.
    """
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
    """
    Refund funds to wallet. Creates a REFUND transaction.
    """
    return credit_wallet(
        user_id, amount,
        description=description,
        reference=reference,
        tx_type=TransactionType.REFUND,
    )


# ---------- Backward-compatible aliases (used by telegrambot.py & tasks.py) ----------

def credit_wallet_balance(user_id, amount):
    """
    Backward-compatible: deducts from wallet (DynoPay's 'useWallet' was a debit).
    Returns a response-like object for compatibility.
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


def create_crypto_payment(user_id, amount, currency, redirect_uri, auto_renewal, top_up):
    """
    Placeholder: Crypto payment creation.
    For now, returns a stub. Replace with real crypto provider (BlockBee, etc.) later.
    """
    logger.warning("create_crypto_payment called — crypto payments not yet integrated with internal wallet")

    class FakeResponse:
        status_code = 501
        text = "Crypto payments are being migrated. Please use wallet balance."
        def json(self):
            return {"message": self.text}

    return FakeResponse()


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
