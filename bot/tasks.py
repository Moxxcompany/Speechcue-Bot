import ast
import logging
import os
from datetime import timedelta
from huey import crontab
from huey.contrib.djhuey import db_task, periodic_task, HUEY
from celery import shared_task
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_celery_beat.models import PeriodicTask, CrontabSchedule
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
    OveragePricingTable,
    UserTransactionLogs,
    TransactionType,
    ManageFreePlanSingleIVRCall,
    UserSubscription,
    SubscriptionPlans,
    DTMF_Inbox,
)
from bot.views import stop_single_active_call, get_call_details
from payment.views import (
    check_user_balance,
    debit_wallet,
    get_user_single_transaction,
)
from translations.translations import (
    SUBSCRIPTION_RENEWED_SUCCESSFULLY,
    EXPIRY_DATE_MESSAGE,
    RENEWAL_FAILED_DUE_TO_INSUFFICIENT_BALANCE,
    FREE_TRIAL_AVAILED,
    SUBSCRIPTION_RENEWAL_MESSAGE,
    RENEWAL_FAILED,
    CAMPAIGN_INITIATED,
)
from user.models import TelegramUser
from .models import CallDuration, BatchCallLogs, CallLogsTable, ReminderTable, ActiveCall
from .utils import (
    get_user_subscription_by_call_id,
    convert_dollars_to_crypto,
    get_user_language,
    extract_call_details,
)
from .call_gate import US_CA_OVERAGE_RATE
from .bot_config import *
from .views import stop_active_batch_calls, stop_single_active_call

logger = logging.getLogger(__name__)

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
    """
    DEPRECATED — Replaced by retell_webhook (call_ended event).
    Kept as no-op for backward compat with existing Celery beat schedules.
    """
    logger.info("check_call_status: DEPRECATED — now handled by Retell webhook (call_ended)")
    return "Handled by webhook"


@shared_task
def call_status_free_plan():
    """
    DEPRECATED — Replaced by retell_webhook (call_ended event).
    Kept as no-op for backward compat with existing Celery beat schedules.
    """
    logger.info("call_status_free_plan: DEPRECATED — now handled by Retell webhook (call_ended)")
    return "Handled by webhook"


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
        wallet = check_user_balance(call_duration.user_id)
        available_balance = wallet["data"]["amount"]
        print(f"wallet balance for user {call_duration.user_id} : {available_balance}")
        lg = user.language
        if float(total_charges) < float(available_balance):
            result = debit_wallet(
                call_duration.user_id, total_charges,
                description=f"Overage: {call_duration.additional_minutes:.2f} extra minutes",
                tx_type="OVR",
            )
            if result["status"] != 200:
                bot.send_message(
                    call_duration.user_id,
                    f"{PROCESSING_ERROR[lg]}\n{result.get('message', '')}",
                )
                return
            print("response 200 debited user wallet")
            transaction_id = result["data"]["transaction_id"]
            print(f"Transaction id in charge_user_for_additional_minutes function : {transaction_id}")

            UserTransactionLogs.objects.create(
                user_id=user,
                reference=transaction_id,
                transaction_type=TransactionType.OVERAGE,
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

    print("Starting subscription status check...")
    current_date = timezone.now().date()
    expired_subscriptions = UserSubscription.objects.filter(
        date_of_expiry__lt=current_date
    )

    print(f"Found {expired_subscriptions.count()} expired subscriptions.")

    for subscription in expired_subscriptions:
        user = subscription.user_id
        telegram_user = TelegramUser.objects.get(user_id=user.user_id)
        lg = get_user_language(user.user_id)
        print(f"Processing subscription for user {user.user_id}...")

        if subscription.auto_renewal:
            print(f"User {user.user_id} has auto-renewal enabled.")
            plan = SubscriptionPlans.objects.get(plan_id=subscription.plan_id_id)

            if plan.plan_price > 0:
                wallet = check_user_balance(user.user_id)
                wallet_balance = wallet["data"]["amount"]
                print(f"User {user.user_id} wallet balance: {wallet_balance}")

                if float(wallet_balance) >= float(plan.plan_price):
                    print(f"User {user.user_id} has sufficient balance for renewal.")
                    result = debit_wallet(
                        user.user_id, plan.plan_price,
                        description=f"Auto-renewal: {plan.name}",
                    )

                    if result["status"] == 200:
                        subscription.date_of_expiry = current_date + timezone.timedelta(
                            days=plan.validity_days
                        )
                        subscription.subscription_status = "active"
                        subscription.save()

                        print(
                            f"Subscription for user {user.user_id} renewed successfully."
                        )
                        bot.send_message(
                            user.user_id,
                            f"🎉 {plan.name} {SUBSCRIPTION_RENEWED_SUCCESSFULLY[lg]}\n"
                            f"{EXPIRY_DATE_MESSAGE[lg]} {subscription.date_of_expiry}.",
                        )
                        subscription.bulk_ivr_calls_left = (
                            plan.number_of_bulk_call_minutes
                        )
                        subscription.single_ivr_left = plan.single_ivr_minutes
                        subscription.date_of_subscription = current_date
                        subscription.call_transfer = plan.call_transfer
                        subscription.save()
                        print(f"user: ", user)
                        print(f"user subscription : {user.subscription_status}")
                        user.subscription_status = "active"
                        print(f"user subscription : {user.subscription_status}")
                        print(f"user plan: {user.plan}")
                        user.plan = plan.name
                        print(f"user plan: {user.plan}")
                        telegram_user.subscription_status = "active"
                        telegram_user.plan = plan.name
                        telegram_user.save()
                        user.save()

                    else:
                        print(
                            f"Renewal failed for user {user.user_id}. Result: {result}"
                        )
                        bot.send_message(
                            user.user_id,
                            f"🚨 {RENEWAL_FAILED[lg]}",
                        )
                        subscription.subscription_status = "inactive"
                        subscription.save()
                else:
                    print(f"User {user.user_id} has insufficient balance for renewal.")
                    subscription.subscription_status = "inactive"
                    subscription.save()
                    bot.send_message(
                        user.user_id,
                        f"⚠️ {RENEWAL_FAILED_DUE_TO_INSUFFICIENT_BALANCE[lg]}",
                    )
            else:
                print(
                    f"User {user.user_id} has availed the free trial, no payment required."
                )
                bot.send_message(
                    user.user_id,
                    f"⚠️ {FREE_TRIAL_AVAILED[lg]}",
                )
                subscription.subscription_status = "inactive"
                subscription.save()

        else:
            print(f"User {user.user_id} does not have auto-renewal enabled.")
            subscription.subscription_status = "inactive"
            subscription.save()
            bot.send_message(user.user_id, SUBSCRIPTION_RENEWAL_MESSAGE[lg])

    print("Subscription status check completed.")


def update_dtmf_inbox(call_details):
    try:
        call_id = call_details["call_id"]
        print(f"Updating DTMF inbox for call ID: {call_id}")
        call_record = DTMF_Inbox.objects.get(call_id=call_id)
        user = TelegramUser.objects.get(user_id=call_record.user_id_id)
        print(f"User found: {user}")
        call_record.timestamp = call_details["timestamp"]
        call_record.dtmf_input = call_details["dtmf_input"]
        call_record.save()
        print(f"Successfully updated DTMF inbox for call ID: {call_details['call_id']}")
    except TelegramUser.DoesNotExist:
        print(f"User with ID {call_details['user_id']} does not exist.")
    except Exception as e:
        print(
            f"Error updating DTMF inbox for call ID {call_details['call_id']}: {str(e)}"
        )


@shared_task
def process_call_logs():
    """
    DEPRECATED — Replaced by retell_webhook (call_ended event).
    DTMF extraction now happens instantly when Retell fires call_ended webhook.
    """
    logger.info("process_call_logs: DEPRECATED — now handled by Retell webhook (call_ended)")
    return "Handled by webhook"


from celery import shared_task
from django.utils import timezone
from .models import ScheduledCalls
from bot.views import bulk_ivr_flow


@shared_task
def send_scheduled_ivr_calls():
    """
    Periodically checks for scheduled IVR calls and triggers the bulk_ivr_flow function
    at the scheduled time. This ensures that either 'task' or 'pathway_id' is passed
    to the IVR flow depending on which one is available in the database.
    """
    current_time = timezone.now()

    # Fetch scheduled calls that are due (schedule_time <= current_time)
    scheduled_calls = ScheduledCalls.objects.filter(schedule_time__lte=current_time)

    print(f"Found {len(scheduled_calls)} scheduled calls to process.")

    for call in scheduled_calls:
        try:
            print(f"Processing scheduled IVR call for user {call.user_id}...")

            if call.task and not call.pathway_id:
                print(f"Passing task: {call.task}")
                bulk_ivr_flow(
                    call.call_data,
                    user_id=call.user_id,
                    caller_id=call.caller_id,
                    task=call.task,
                )
            elif not call.task and call.pathway_id:
                # If pathway_id exists and task is null, pass pathway_id to the IVR flow
                print(f"Passing pathway_id: {call.pathway_id}")
                bulk_ivr_flow(
                    call.call_data,
                    user_id=call.user_id,
                    caller_id=call.caller_id,
                    pathway_id=call.pathway_id,
                )
            else:
                print(
                    f"Both task and pathway_id are missing for user {call.user_id}, skipping."
                )
                continue

            # Optionally mark the call as sent or update its status
            call.call_status = "sent"  # Update call status to 'sent'
            call.save()
            print(f"Scheduled IVR call for user {call.user_id} has been sent.")

        except Exception as e:
            print(
                f"Error processing scheduled IVR call for user {call.user_id}: {str(e)}"
            )

    print("Finished processing scheduled IVR calls.")


# --------------------------HUEY-----------------------------------
@db_task()
def execute_bulk_ivr(scheduled_call_id):
    """
    Huey task to execute the bulk_ivr_flow function at the scheduled time.
    """

    try:
        # Fetch the scheduled call details
        scheduled_call = ScheduledCalls.objects.get(id=scheduled_call_id)
        if scheduled_call.canceled:
            print(f"Scheduled call {scheduled_call_id} has been canceled.")
            return
        try:
            call_data = ast.literal_eval(
                scheduled_call.call_data
            )  # Safely evaluate the string to a list
            if not isinstance(call_data, list):
                raise ValueError("call_data must be a list.")
                print("Converted call_data:", call_data)
        except Exception as e:
            print(f"Error converting call_data: {str(e)}")

        response = bulk_ivr_flow(
            call_data=call_data,
            user_id=str(scheduled_call.user_id_id),
            caller_id=scheduled_call.caller_id,
            campaign_id=str(scheduled_call.campaign_id_id),
            task=scheduled_call.task,
            pathway_id=scheduled_call.pathway_id,
        )

        scheduled_call.call_status = True
        scheduled_call.save()
        lg = get_user_language(scheduled_call.user_id_id)
        if response.status_code != 200:
            bot.send_message(
                scheduled_call.user_id_id,
                f"Failed to initiate campaign {scheduled_call.campaign_id.campaign_name}.",
            )
            return
        bot.send_message(scheduled_call.user_id_id, CAMPAIGN_INITIATED[lg])

    except ScheduledCalls.DoesNotExist:
        print(f"Scheduled call with ID {scheduled_call_id} does not exist.")
    except Exception as e:
        print(f"Error occurred while processing scheduled call: {str(e)}")


@db_task()
def send_reminder(scheduled_call_id, reminder_time):
    """
    Huey task to send a reminder for a scheduled call.
    """
    try:
        # Fetch the scheduled call
        scheduled_call = ScheduledCalls.objects.get(id=scheduled_call_id)

        # Check if the call has been canceled or already executed
        if scheduled_call.canceled or scheduled_call.call_status:
            print(
                f"Call {scheduled_call_id} is canceled or already executed. Skipping reminder."
            )
            return

        # Send the reminder (e.g., via Telegram bot)
        user_id = scheduled_call.user_id.user_id
        reminder_message = (
            f"Reminder: Your call is scheduled at {scheduled_call.schedule_time}.\n"
            f"Time left: {reminder_time} minutes."
        )
        bot.send_message(user_id, reminder_message)

        # Mark the reminder as sent (if using the Reminder model)
        reminder = ReminderTable.objects.create(
            scheduled_call=scheduled_call,
            reminder_time=scheduled_call.schedule_time
            - timedelta(minutes=reminder_time),
            sent=True,
        )
        reminder.save()

        print(f"Reminder sent for call {scheduled_call_id}.")

    except ScheduledCalls.DoesNotExist:
        print(f"Scheduled call with ID {scheduled_call_id} does not exist.")
    except Exception as e:
        print(f"Error sending reminder: {str(e)}")


def cancel_scheduled_call(scheduled_call_id):
    """
    Cancel a scheduled call by its ID.
    """
    try:
        # Fetch the scheduled call
        scheduled_call = ScheduledCalls.objects.get(id=scheduled_call_id)

        # Check if the call has already been executed or canceled
        if scheduled_call.call_status:
            bot.send_message(
                scheduled_call.user_id_id, "Campaign is active and cannot be canceled."
            )
            return

        if scheduled_call.canceled:
            print("Campaign has already been canceled.")
            return

        task = HUEY.get_task_by_id(f"execute_bulk_ivr:{scheduled_call_id}")
        if task:
            task.revoke()

        scheduled_call.canceled = True
        scheduled_call.save()

        return "Call successfully canceled."

    except ScheduledCalls.DoesNotExist:
        return "Scheduled call not found."
    except Exception as e:
        return f"Error canceling scheduled call: {str(e)}"
