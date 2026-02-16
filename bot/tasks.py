import ast
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
from .models import CallDuration, BatchCallLogs, CallLogsTable, ReminderTable
from .utils import (
    get_user_subscription_by_call_id,
    convert_crypto_to_usd,
    convert_dollars_to_crypto,
    get_user_language,
    extract_call_details,
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
                            f"Renewal failed for user {user.user_id}. Response: {response.text}"
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
    Fetch call details for all calls in the CallLogsTable, extract required information,
    and update the DTMF_Inbox table.
    """
    processed_call_ids = DTMF_Inbox.objects.values_list("call_id", flat=True)
    all_calls = CallLogsTable.objects.exclude(call_id__in=processed_call_ids)

    print(f"Starting process_call_logs task. Total calls to process: {len(all_calls)}")

    for call in all_calls:
        try:
            print(f"Fetching details for call ID: {call.call_id}")
            call_data = get_call_details(call.call_id)
            if not call_data:
                print(f"No call details found for call ID: {call.call_id}")
                continue

            print(f"Extracting details for call ID: {call.call_id}")
            extracted_details = extract_call_details(call_data)
            extracted_details["user_id"] = call.user_id
            print(f"Extracted details: {extracted_details}")

            update_dtmf_inbox(extracted_details)
            print(f"Finished processing call ID: {call.call_id}")
        except Exception as e:
            print(f"Error processing call ID {call.call_id}: {str(e)}")


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
