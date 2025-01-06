import os

from celery import shared_task
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from dotenv.main import load_dotenv

from TelegramBot.English import (
    PROCESSING_ERROR,
    INSUFFICIENT_BALANCE_FOR_PAYMENT,
    WALLET_BALANCE,
    WALLET_TOP_UP,
    ADDITIONAL_MINUTES,
    CHARGED_SUCCESSFULLY,
)
from TelegramBot.crypto_cache import *
from payment.models import (
    VirtualAccountsTable,
    OveragePricingTable,
    UserTransactionLogs,
    MainWalletTable,
    TransactionType,
    ManageFreePlanSingleIVRCall,
    UserSubscription,
    SubscriptionPlans,
)
from bot.views import stop_single_active_call
from payment.views import (
    check_user_balance,
    credit_wallet_balance,
    get_user_single_transaction,
)
from user.models import TelegramUser
from .models import CallDuration, BatchCallLogs
from .utils import (
    get_user_subscription_by_call_id,
    convert_crypto_to_usd,
    convert_dollars_to_crypto,
    get_user_language,
)
from .bot_config import *
from .views import stop_active_batch_calls

load_dotenv()


def update_batch_calls_status_to_terminated(batch_id, started_at):
    calls = BatchCallLogs.objects.filter(batch_id=batch_id)

    current_time = timezone.now()

    for call in calls:
        if call.queue_status in ["queued", "new", "started"]:
            ongoing_duration_seconds = (current_time - started_at).total_seconds()
            ongoing_duration_minutes = ongoing_duration_seconds / 60

            if ongoing_duration_minutes > 0:
                difference = ongoing_duration_minutes
                call.additional_minutes = difference
            else:
                call.additional_minutes = 0
            call.queue_status = "terminated"
            call.end_time = current_time
            call.save()


@shared_task
def check_call_status():
    bland_api_key = os.getenv("BLAND_API_KEY")
    print("Starting check_call_status task with API key: ", bland_api_key)

    tracked_calls = BatchCallLogs.objects.filter(
        call_status__in=["new", "queued", "started"]
    )

    for call in tracked_calls:
        headers = {"authorization": f"{bland_api_key}"}

        try:
            response = fetch_with_retry(
                f"https://api.bland.ai/v1/calls/{call.call_id}", headers
            )
            print(f"Processing call ID: {call.call_id}")
        except ValueError as e:
            print(f"Failed to fetch call details: {str(e)}")
            continue

        call_data = response.json()
        queue_status = call_data.get("queue_status", "")
        started_at_str = call_data.get("started_at", None)
        end_at_str = call_data.get("end_at", None)
        call_length = call_data.get("call_length", None)
        print(
            f"queue_status: {queue_status}, "
            f"started_at_str: {started_at_str}, "
            f"end_at_str: {end_at_str}, "
            f"call_length: {call_length}"
        )

        started_at = parse_datetime(started_at_str) if started_at_str else None
        end_at = parse_datetime(end_at_str) if end_at_str else None
        subscription_result = get_user_subscription_by_call_id(call.call_id)

        if subscription_result["status"] != "Success":
            print(subscription_result["status"])
            continue

        user_subscription = subscription_result["user_subscription"]
        bulk_ivr_calls_left = user_subscription.bulk_ivr_calls_left

        if queue_status == "started" and started_at:
            current_time = timezone.now()
            ongoing_duration_seconds = (current_time - started_at).total_seconds()
            ongoing_duration_minutes = ongoing_duration_seconds / 60

            if ongoing_duration_minutes >= bulk_ivr_calls_left:
                stop_response = stop_active_batch_calls(call.batch_id)

                if stop_response.status_code == 200:
                    print(f"Batch {call.batch_id} has been terminated.")

                    update_batch_calls_status_to_terminated(call.batch_id, started_at)
                    user_subscription.bulk_ivr_calls_left = 0
                    user_subscription.save()
                else:
                    print(
                        f"Failed to terminate call {call.call_id}. Response: {stop_response.content}"
                    )
            else:
                print(
                    f"Call {call.call_id} is within the allowed IVR minutes, letting it continue."
                )

        elif queue_status == "complete" and started_at and end_at:
            duration_in_seconds = (end_at - started_at).total_seconds()
            duration_in_minutes = duration_in_seconds / 60

            if duration_in_minutes > bulk_ivr_calls_left:
                difference = float(duration_in_minutes) - float(bulk_ivr_calls_left)
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id,
                    pathway_id=call.pathway_id,
                    defaults={
                        "start_time": started_at,
                        "end_time": end_at,
                        "queue_status": queue_status,
                        "duration_in_seconds": duration_in_seconds,
                        "additional_minutes": f"{difference}",
                        "user_id": subscription_result["user_id"],
                    },
                )
                user_subscription.bulk_ivr_calls_left = 0
                user_subscription.save()
            else:
                remaining_minutes = float(bulk_ivr_calls_left) - float(
                    duration_in_minutes
                )
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id,
                    pathway_id=call.pathway_id,
                    defaults={
                        "start_time": started_at,
                        "end_time": end_at,
                        "queue_status": queue_status,
                        "duration_in_seconds": duration_in_seconds,
                        "additional_minutes": 0,
                        "user_id": subscription_result["user_id"],
                    },
                )
                user_subscription.bulk_ivr_calls_left = remaining_minutes
                user_subscription.save()

            call.call_status = queue_status
            call.save()


@shared_task
def call_status_free_plan():
    bland_api_key = os.getenv("BLAND_API_KEY")
    tracked_calls = ManageFreePlanSingleIVRCall.objects.filter(
        call_status__in=["new", "queued", "started"]
    )
    for call in tracked_calls:
        headers = {"authorization": f"{bland_api_key}"}
        try:
            response = fetch_with_retry(
                f"https://api.bland.ai/v1/calls/{call.call_id}", headers
            )
            print(f"Processing call ID: {call.call_id}")
        except ValueError as e:
            print(f"Failed to fetch call details: {str(e)}")
            continue

        call_data = response.json()
        queue_status = call_data.get("queue_status", "")
        started_at_str = call_data.get("started_at", None)
        end_at_str = call_data.get("end_at", None)
        call_length = call_data.get("call_length", None)
        print(
            f"queue_status: {queue_status}, started_at_str: {started_at_str}, end_at_str: {end_at_str}, call_length: {call_length}"
        )

        started_at = parse_datetime(started_at_str) if started_at_str else None
        end_at = parse_datetime(end_at_str) if end_at_str else None
        subscription_result = get_user_subscription_by_call_id(call.call_id)

        if subscription_result["status"] != "Success":
            print(subscription_result["status"])
            continue

        user_subscription = subscription_result["user_subscription"]
        single_ivr_left = user_subscription.single_ivr_left

        if queue_status == "started" and started_at:
            current_time = timezone.now()
            ongoing_duration_seconds = (current_time - started_at).total_seconds()
            ongoing_duration_minutes = ongoing_duration_seconds / 60

            if ongoing_duration_minutes >= single_ivr_left:
                difference = ongoing_duration_minutes - single_ivr_left
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id,
                    pathway_id=call.pathway_id,
                    defaults={
                        "start_time": started_at,
                        "queue_status": queue_status,
                        "duration_in_seconds": ongoing_duration_seconds,
                        "additional_minutes": 0,
                        "user_id": subscription_result["user_id"],
                    },
                )

                stop_response = stop_single_active_call(call.call_id)
                if stop_response.status_code == 200:
                    print(f"Call {call.call_id} has been terminated.")
                    user_subscription.single_ivr_left = 0
                    user_subscription.save()
                    call_duration_record.queue_status = "terminated"
                    call_duration_record.end_time = current_time
                    call_duration_record.additional_minutes = difference
                    call_duration_record.save()
                    call.call_status = "terminated"
                    call.save()
                else:
                    print(
                        f"Failed to terminate call {call.call_id}. Response: {stop_response.content}"
                    )
            else:
                print(
                    f"Call {call.call_id} is within the allowed IVR minutes, letting it continue."
                )

        elif queue_status == "complete" and started_at and end_at:
            duration_in_seconds = (end_at - started_at).total_seconds()
            duration_in_minutes = duration_in_seconds / 60

            if float(duration_in_minutes) > float(single_ivr_left):
                difference = float(duration_in_minutes) - float(single_ivr_left)
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id,
                    pathway_id=call.pathway_id,
                    defaults={
                        "start_time": started_at,
                        "end_time": end_at,
                        "queue_status": queue_status,
                        "duration_in_seconds": duration_in_seconds,
                        "additional_minutes": f"{difference}",
                        "user_id": subscription_result["user_id"],
                    },
                )
                user_subscription.single_ivr_left = 0
                user_subscription.save()
            else:
                remaining_minutes = float(single_ivr_left) - float(duration_in_minutes)
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id,
                    pathway_id=call.pathway_id,
                    defaults={
                        "start_time": started_at,
                        "end_time": end_at,
                        "queue_status": queue_status,
                        "duration_in_seconds": duration_in_seconds,
                        "additional_minutes": 0,
                        "user_id": subscription_result["user_id"],
                    },
                )
                user_subscription.single_ivr_left = remaining_minutes
                user_subscription.save()

            call.call_status = queue_status
            call.save()


@shared_task
def charge_user_for_additional_minutes():
    print("Charge_user_for_additional_minutes RUNNING..... ")

    calls_with_additional_minutes = CallDuration.objects.filter(
        additional_minutes__gt=0, charged=False
    )

    for call_duration in calls_with_additional_minutes:
        user = TelegramUser.objects.get(user_id=call_duration.user_id)
        overage_pricing = OveragePricingTable.objects.get(pricing_unit="MIN")
        price_per_min = float(overage_pricing.overage_pricing)
        total_charges = price_per_min * call_duration.additional_minutes
        print(f"total charges for call id {call_duration.call_id} : {total_charges}")
        wallet_balance = check_user_balance(call_duration.user_id)
        print(f"wallet balance for user {call_duration.user_id} : {wallet_balance}")
        wallet = wallet_balance.json()
        available_balance = wallet["data"]["amount"]
        lg = user.language
        if float(total_charges) < float(available_balance):
            response = credit_wallet_balance(call_duration.user_id, total_charges)
            if response.status_code != 200:
                bot.send_message(
                    call_duration.user_id,
                    f"{PROCESSING_ERROR[lg]}\n" f"{response.text}",
                )
                return
            print("response 200 crediting user wallet ")

            print(f"response data : {response.text}")
            data = response.json()
            transaction_id = data["data"]["transaction_id"]
            print(
                f"Transaction id in charge_user_for_additional_minutes function : {transaction_id}"
            )
            response = get_user_single_transaction(
                call_duration.user_id, transaction_id
            )
            if response.status_code == 200:
                transaction_data = response.json()

                payment_reference = transaction_data["data"]["transaction_reference"]
                UserTransactionLogs.objects.create(
                    user_id=user,
                    reference=payment_reference,
                    transaction_type=TransactionType.Overage,
                )
                call_duration.charged = True
                call_duration.save()
                break


@shared_task()
def notify_users():
    print("Notifying users.....")

    call_records_paid = CallDuration.objects.filter(notified=False, charged=True)
    users_with_paid_minutes = call_records_paid.values("user_id").annotate(
        total_paid_minutes=Sum("additional_minutes")
    )

    call_records_unpaid = CallDuration.objects.filter(notified=False, charged=False)
    users_with_unpaid_minutes = call_records_unpaid.values("user_id").annotate(
        total_unpaid_minutes=Sum("additional_minutes")
    )

    for user in users_with_paid_minutes:

        user_id = user["user_id"]
        lg = TelegramUser.objects.get(user_id=user_id).language

        paid_minutes = user["total_paid_minutes"]
        bot.send_message(user_id, f"{CHARGED_SUCCESSFULLY[lg]} {paid_minutes:.4f} ")
        CallDuration.objects.filter(
            user_id=user_id, charged=True, notified=False
        ).update(notified=True)

    for user in users_with_unpaid_minutes:
        user_id = user["user_id"]
        lg = TelegramUser.objects.get(user_id=user_id).language
        unpaid_minutes = user["total_unpaid_minutes"]
        if unpaid_minutes > 0:
            bot.send_message(
                user_id,
                f"{INSUFFICIENT_BALANCE_FOR_PAYMENT[lg]} {unpaid_minutes:.4f} {ADDITIONAL_MINUTES[lg]}"
                f"{WALLET_TOP_UP[lg]}",
            )


@shared_task
def check_subscription_status():
    """
    Daily task to check subscription expiry and handle auto-renewals.
    """
    print("Starting subscription status check...")
    current_date = timezone.now().date()
    expired_subscriptions = UserSubscription.objects.filter(
        date_of_expiry__lt=current_date, subscription_status="active"
    )

    print(f"Found {expired_subscriptions.count()} expired subscriptions.")

    for subscription in expired_subscriptions:
        user = subscription.user_id
        lg = get_user_language(user.user_id)
        print(f"Processing subscription for user {user.user_id}...")

        if subscription.auto_renewal:
            print(f"User {user.user_id} has auto-renewal enabled.")
            plan = SubscriptionPlans.objects.get(plan_id=subscription.plan_id_id)
            wallet_balance = check_user_balance(user.user_id).json()["data"]["amount"]
            print(f"User {user.user_id} wallet balance: {wallet_balance}")

            if float(wallet_balance) >= float(plan.plan_price):
                print(f"User {user.user_id} has sufficient balance for renewal.")
                response = credit_wallet_balance(user.user_id, plan.plan_price)

                if response.status_code == 200:
                    subscription.date_of_expiry = current_date + timezone.timedelta(
                        days=plan.validity_days
                    )
                    subscription.subscription_status = "active"
                    subscription.save()

                    print(f"Subscription for user {user.user_id} renewed successfully.")
                    bot.send_message(
                        user.user_id,
                        f"🎉 {plan.name} subscription renewed successfully!\n"
                        f"Your new expiry date is {subscription.date_of_expiry}.",
                    )
                else:
                    print(
                        f"Renewal failed for user {user.user_id}. Response: {response.text}"
                    )
                    bot.send_message(
                        user.user_id,
                        f"🚨 Renewal failed due to processing error.\n"
                        f"Please contact support or try again manually.",
                    )
                    subscription.subscription_status = "inactive"
                    subscription.save()
            else:
                print(f"User {user.user_id} has insufficient balance for renewal.")
                subscription.subscription_status = "inactive"
                subscription.save()
                bot.send_message(
                    user.user_id,
                    f"⚠️ Your subscription has expired, and your wallet balance is insufficient for renewal.\n"
                    f"Please top up your wallet to reactivate your plan.",
                )
        else:
            print(f"User {user.user_id} does not have auto-renewal enabled.")
            subscription.subscription_status = "inactive"
            subscription.save()
            bot.send_message(
                user.user_id,
                f"⚠️ Your subscription has expired.\n"
                f"Please renew it manually to continue enjoying our services.",
            )

    print("Subscription status check completed.")
