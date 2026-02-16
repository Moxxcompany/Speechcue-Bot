"""
Pre-Call Gate — Enforces balance/minute checks before allowing any call.

Usage:
    from bot.call_gate import pre_call_check

    result = pre_call_check(user_id, phone_number, call_type="single")
    if not result["allowed"]:
        bot.send_message(user_id, result["message"])
        return
    # proceed with call...
"""
import logging
import re
from decimal import Decimal

from django.conf import settings
from payment.models import UserSubscription, SubscriptionPlans
from user.models import TelegramUser

logger = logging.getLogger(__name__)

# =============================================================================
# International Rate Table — per-minute charge to user (wallet deduction)
# =============================================================================
INTERNATIONAL_RATES = {
    # prefix: (region_name, rate_per_minute)
    "+1":   ("US/Canada",           Decimal("0.00")),   # included in plan
    "+44":  ("UK",                  Decimal("0.45")),
    "+33":  ("France",              Decimal("0.45")),
    "+49":  ("Germany",             Decimal("0.45")),
    "+34":  ("Spain",               Decimal("0.45")),
    "+39":  ("Italy",               Decimal("0.45")),
    "+31":  ("Netherlands",         Decimal("0.45")),
    "+32":  ("Belgium",             Decimal("0.45")),
    "+41":  ("Switzerland",         Decimal("0.45")),
    "+43":  ("Austria",             Decimal("0.45")),
    "+46":  ("Sweden",              Decimal("0.45")),
    "+47":  ("Norway",              Decimal("0.45")),
    "+45":  ("Denmark",             Decimal("0.45")),
    "+358": ("Finland",             Decimal("0.45")),
    "+353": ("Ireland",             Decimal("0.45")),
    "+351": ("Portugal",            Decimal("0.45")),
    "+48":  ("Poland",              Decimal("0.45")),
    "+420": ("Czech Republic",      Decimal("0.45")),
    "+91":  ("India",               Decimal("0.45")),
    "+86":  ("China",               Decimal("0.45")),
    "+65":  ("Singapore",           Decimal("0.45")),
    "+66":  ("Thailand",            Decimal("0.45")),
    "+84":  ("Vietnam",             Decimal("0.45")),
    "+60":  ("Malaysia",            Decimal("0.45")),
    "+62":  ("Indonesia",           Decimal("0.45")),
    "+63":  ("Philippines",         Decimal("0.45")),
    "+81":  ("Japan",               Decimal("0.55")),
    "+82":  ("South Korea",         Decimal("0.55")),
    "+61":  ("Australia",           Decimal("0.55")),
    "+64":  ("New Zealand",         Decimal("0.55")),
    "+52":  ("Mexico",              Decimal("0.65")),
    "+55":  ("Brazil",              Decimal("0.65")),
    "+54":  ("Argentina",           Decimal("0.65")),
    "+57":  ("Colombia",            Decimal("0.65")),
    "+56":  ("Chile",               Decimal("0.65")),
    "+51":  ("Peru",                Decimal("0.65")),
    "+58":  ("Venezuela",           Decimal("0.65")),
    "+966": ("Saudi Arabia",        Decimal("0.60")),
    "+971": ("UAE",                 Decimal("0.60")),
    "+972": ("Israel",              Decimal("0.60")),
    "+90":  ("Turkey",              Decimal("0.60")),
    "+974": ("Qatar",               Decimal("0.60")),
    "+973": ("Bahrain",             Decimal("0.60")),
    "+968": ("Oman",                Decimal("0.60")),
    "+234": ("Nigeria",             Decimal("0.85")),
    "+254": ("Kenya",               Decimal("0.85")),
    "+27":  ("South Africa",        Decimal("0.85")),
    "+20":  ("Egypt",               Decimal("0.85")),
    "+233": ("Ghana",               Decimal("0.85")),
    "+256": ("Uganda",              Decimal("0.85")),
    "+255": ("Tanzania",            Decimal("0.85")),
    "+251": ("Ethiopia",            Decimal("0.85")),
    "+212": ("Morocco",             Decimal("0.85")),
    "+213": ("Algeria",             Decimal("0.85")),
    "+216": ("Tunisia",             Decimal("0.85")),
}

# Default rate for unlisted countries
DEFAULT_INTERNATIONAL_RATE = Decimal("0.70")

# Overage rate for US/Canada when plan minutes exhausted
US_CA_OVERAGE_RATE = Decimal("0.35")

# Minimum minutes to pre-check (2 min buffer)
MIN_MINUTES_BUFFER = 2


def classify_destination(phone_number):
    """
    Classify a phone number by region. Returns (region_name, rate_per_minute, is_domestic).
    Domestic = US/Canada (+1).
    """
    cleaned = re.sub(r"[\s\-\(\)]", "", str(phone_number))
    if not cleaned.startswith("+"):
        # Assume US/Canada if no country code
        return "US/Canada", Decimal("0.00"), True

    # Match longest prefix first (e.g., +966 before +9)
    best_match = None
    best_len = 0
    for prefix, (region, rate) in INTERNATIONAL_RATES.items():
        if cleaned.startswith(prefix) and len(prefix) > best_len:
            best_match = (region, rate)
            best_len = len(prefix)

    if best_match:
        region, rate = best_match
        is_domestic = (rate == Decimal("0.00"))
        return region, rate, is_domestic

    return "International", DEFAULT_INTERNATIONAL_RATE, False


def pre_call_check(user_id, phone_number, call_type="single", num_calls=1):
    """
    Pre-call gate. Returns dict:
        {
            "allowed": True/False,
            "message": "..." (reason if blocked),
            "region": "US/Canada" | "UK" | etc.,
            "rate": Decimal per minute (0 for domestic plan-covered),
            "is_domestic": True/False,
            "billing_source": "plan" | "wallet" | "blocked",
        }
    """
    region, rate, is_domestic = classify_destination(phone_number)

    try:
        user = TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        return _blocked(region, rate, is_domestic, "User not found. Please /start first.")

    wallet_balance = user.wallet_balance or Decimal("0.00")

    # Get subscription
    try:
        subscription = UserSubscription.objects.get(user_id=user_id)
        has_active_sub = subscription.subscription_status == "active"
    except UserSubscription.DoesNotExist:
        subscription = None
        has_active_sub = False

    # ── FREE PLAN ──
    if has_active_sub and subscription.plan_id and subscription.plan_id.plan_price == 0:
        if not is_domestic:
            return _blocked(region, rate, is_domestic,
                "International calls are not available on the Free Trial. "
                "Please upgrade to a paid plan.")

        single_left = float(subscription.single_ivr_left or 0)
        if single_left < 1:
            return _blocked(region, rate, is_domestic,
                "Free Trial minutes exhausted. Please upgrade to continue calling.")

        return _allowed(region, Decimal("0.00"), True, "plan")

    # ── INTERNATIONAL CALL (any plan or pay-as-you-go) ──
    if not is_domestic:
        required = rate * MIN_MINUTES_BUFFER * num_calls
        if wallet_balance < required:
            return _blocked(region, rate, is_domestic,
                f"Insufficient wallet balance for {region} call.\n"
                f"Rate: ${rate}/min | Required: ${required:.2f} (2 min x {num_calls} calls)\n"
                f"Your balance: ${wallet_balance:.2f}\n"
                f"Please top up your wallet.")

        return _allowed(region, rate, False, "wallet")

    # ── DOMESTIC (US/Canada) WITH ACTIVE SUBSCRIPTION ──
    if has_active_sub and subscription.plan_id:
        if call_type == "single":
            single_left = float(subscription.single_ivr_left or 0)
            if single_left >= MIN_MINUTES_BUFFER:
                return _allowed(region, Decimal("0.00"), True, "plan")
            # Single IVR exhausted — fall through to wallet/overage check

        elif call_type == "bulk":
            bulk_left = float(subscription.bulk_ivr_calls_left or 0)
            if bulk_left >= MIN_MINUTES_BUFFER * num_calls:
                return _allowed(region, Decimal("0.00"), True, "plan")
            # Bulk exhausted — fall through to wallet/overage check

        # Plan minutes exhausted — check wallet for overage
        required = US_CA_OVERAGE_RATE * MIN_MINUTES_BUFFER * num_calls
        if wallet_balance >= required:
            return _allowed(region, US_CA_OVERAGE_RATE, True, "wallet")

        return _blocked(region, US_CA_OVERAGE_RATE, True,
            f"Plan minutes exhausted.\n"
            f"Overage rate: ${US_CA_OVERAGE_RATE}/min | Required: ${required:.2f}\n"
            f"Your balance: ${wallet_balance:.2f}\n"
            f"Please top up your wallet or upgrade your plan.")

    # ── PAY-AS-YOU-GO (no active subscription) ──
    required = US_CA_OVERAGE_RATE * MIN_MINUTES_BUFFER * num_calls
    if wallet_balance >= required:
        return _allowed(region, US_CA_OVERAGE_RATE, True, "wallet")

    return _blocked(region, US_CA_OVERAGE_RATE, True,
        f"No active subscription.\n"
        f"Pay-as-you-go rate: ${US_CA_OVERAGE_RATE}/min | Required: ${required:.2f}\n"
        f"Your balance: ${wallet_balance:.2f}\n"
        f"Please top up your wallet or subscribe to a plan.")


def pre_call_check_bulk(user_id, phone_numbers, call_type="bulk"):
    """
    Pre-call gate for bulk/batch calls. Checks all numbers.
    Groups by domestic vs international and validates total cost.
    """
    domestic_count = 0
    intl_cost = Decimal("0.00")
    intl_numbers = []

    for entry in phone_numbers:
        phone = entry.get("phone_number", entry.get("to_number", "")) if isinstance(entry, dict) else str(entry)
        region, rate, is_domestic = classify_destination(phone)
        if is_domestic:
            domestic_count += 1
        else:
            intl_cost += rate * MIN_MINUTES_BUFFER
            intl_numbers.append((phone, region, rate))

    try:
        user = TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        return {"allowed": False, "message": "User not found.", "domestic_count": 0, "intl_count": 0}

    wallet_balance = user.wallet_balance or Decimal("0.00")

    # Check domestic bulk minutes
    try:
        subscription = UserSubscription.objects.get(user_id=user_id)
        has_active_sub = subscription.subscription_status == "active"
    except UserSubscription.DoesNotExist:
        subscription = None
        has_active_sub = False

    domestic_ok = True
    domestic_wallet_needed = Decimal("0.00")

    if domestic_count > 0:
        if has_active_sub and subscription.plan_id and subscription.plan_id.plan_price > 0:
            bulk_left = float(subscription.bulk_ivr_calls_left or 0)
            if bulk_left < MIN_MINUTES_BUFFER * domestic_count:
                domestic_wallet_needed = US_CA_OVERAGE_RATE * MIN_MINUTES_BUFFER * domestic_count
        else:
            domestic_wallet_needed = US_CA_OVERAGE_RATE * MIN_MINUTES_BUFFER * domestic_count

    total_wallet_needed = intl_cost + domestic_wallet_needed
    if total_wallet_needed > 0 and wallet_balance < total_wallet_needed:
        return {
            "allowed": False,
            "message": (
                f"Insufficient wallet balance for batch call.\n"
                f"Domestic calls: {domestic_count} | International: {len(intl_numbers)}\n"
                f"Required: ${total_wallet_needed:.2f} | Balance: ${wallet_balance:.2f}\n"
                f"Please top up your wallet."
            ),
            "domestic_count": domestic_count,
            "intl_count": len(intl_numbers),
        }

    return {
        "allowed": True,
        "message": "OK",
        "domestic_count": domestic_count,
        "intl_count": len(intl_numbers),
        "intl_cost_estimate": intl_cost,
    }


def _allowed(region, rate, is_domestic, billing_source):
    return {
        "allowed": True,
        "message": "OK",
        "region": region,
        "rate": rate,
        "is_domestic": is_domestic,
        "billing_source": billing_source,
    }


def _blocked(region, rate, is_domestic, message):
    return {
        "allowed": False,
        "message": message,
        "region": region,
        "rate": rate,
        "is_domestic": is_domestic,
        "billing_source": "blocked",
    }
