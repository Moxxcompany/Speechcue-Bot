import os

from celery import shared_task
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from dotenv.main import load_dotenv

from TelegramBot.crypto_cache import *
from payment.models import VirtualAccountsTable, OveragePricingTable, UserTransactionLogs, MainWalletTable, \
    TransactionType

from user.models import TelegramUser
from .models import CallLogsTable, CallDuration
from payment.views import stop_single_active_call, get_account_balance, send_payment, x_api_key
from .utils import get_user_subscription_by_call_id, convert_crypto_to_usd, convert_dollars_to_crypto
from .bot_config import *
load_dotenv()




@shared_task
def check_call_status():
    bland_api_key = os.getenv('BLAND_API_KEY')
    print("Starting check_call_status task with API key: ", bland_api_key)

    tracked_calls = CallLogsTable.objects.filter(call_status__in=['new', 'queued', 'started'])

    for call in tracked_calls:
        headers = {"authorization": f"{bland_api_key}"}
        try:
            response = fetch_with_retry(f"https://api.bland.ai/v1/calls/{call.call_id}", headers)
            print(f"Processing call ID: {call.call_id}")
        except ValueError as e:
            print(f"Failed to fetch call details: {str(e)}")
            continue

        call_data = response.json()
        queue_status = call_data.get('queue_status', '')
        started_at_str = call_data.get('started_at', None)
        end_at_str = call_data.get('end_at', None)
        call_length = call_data.get('call_length', None)
        print(
            f"queue_status: {queue_status}, started_at_str: {started_at_str}, end_at_str: {end_at_str}, call_length: {call_length}")

        started_at = parse_datetime(started_at_str) if started_at_str else None
        end_at = parse_datetime(end_at_str) if end_at_str else None
        subscription_result = get_user_subscription_by_call_id(call.call_id)

        if subscription_result['status'] != 'Success':
            print(subscription_result['status'])
            continue

        user_subscription = subscription_result['user_subscription']
        bulk_ivr_calls_left = user_subscription.bulk_ivr_calls_left

        if queue_status == 'started' and started_at:
            current_time = timezone.now()
            ongoing_duration_seconds = (current_time - started_at).total_seconds()
            ongoing_duration_minutes = ongoing_duration_seconds / 60

            if ongoing_duration_minutes >= bulk_ivr_calls_left:
                difference = ongoing_duration_minutes - bulk_ivr_calls_left
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id, pathway_id=call.pathway_id,
                    defaults={
                        'start_time': started_at, 'queue_status': queue_status,
                        'duration_in_seconds': ongoing_duration_seconds, 'additional_minutes': 0,
                        'user_id': subscription_result['user_id']
                    }
                )

                stop_response = stop_single_active_call(call.call_id)
                if stop_response.status_code == 200:
                    print(f"Call {call.call_id} has been terminated.")
                    user_subscription.bulk_ivr_calls_left = 0
                    user_subscription.save()
                    call_duration_record.queue_status = 'terminated'
                    call_duration_record.end_time = current_time
                    call_duration_record.additional_minutes = difference
                    call_duration_record.save()
                    call.call_status = 'terminated'
                    call.save()
                else:
                    print(f"Failed to terminate call {call.call_id}. Response: {stop_response.content}")
            else:
                print(f"Call {call.call_id} is within the allowed IVR minutes, letting it continue.")

        elif queue_status == 'complete' and started_at and end_at:
            duration_in_seconds = (end_at - started_at).total_seconds()
            duration_in_minutes = duration_in_seconds / 60

            if duration_in_minutes > bulk_ivr_calls_left:
                difference = duration_in_minutes - bulk_ivr_calls_left
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id, pathway_id=call.pathway_id,
                    defaults={
                        'start_time': started_at, 'end_time': end_at, 'queue_status': queue_status,
                        'duration_in_seconds': duration_in_seconds, 'additional_minutes': f"{difference}",
                        'user_id': subscription_result['user_id']
                    }
                )
                user_subscription.bulk_ivr_calls_left = 0
                user_subscription.save()
            else:
                remaining_minutes = bulk_ivr_calls_left - duration_in_minutes
                call_duration_record, created = CallDuration.objects.update_or_create(
                    call_id=call.call_id, pathway_id=call.pathway_id,
                    defaults={
                        'start_time': started_at, 'end_time': end_at, 'queue_status': queue_status,
                        'duration_in_seconds': duration_in_seconds, 'additional_minutes': 0,
                        'user_id': subscription_result['user_id']
                    }
                )
                user_subscription.bulk_ivr_calls_left = remaining_minutes
                user_subscription.save()

            call.call_status = queue_status
            call.save()







@shared_task
def charge_user_for_additional_minutes():
    print("Charge_user_for_additional_minutes RUNNING..... ")

    calls_with_additional_minutes = CallDuration.objects.filter(additional_minutes__gt=0, charged=False)

    for call_duration in calls_with_additional_minutes:
        user = TelegramUser.objects.get(user_id=call_duration.user_id)
        overage_pricing = OveragePricingTable.objects.get(pricing_unit='MIN')
        price_per_min = float(overage_pricing.overage_pricing)
        total_charges = price_per_min * call_duration.additional_minutes

        accounts = VirtualAccountsTable.objects.filter(user_id=user)

        for account in accounts:
            balance_response = get_account_balance(account.account_id)
            if balance_response.status_code != 200:
                continue

            available_balance = float(balance_response.json()["availableBalance"])
            acc_currency = account.currency.lower()

            price_in_usd = None
            if acc_currency == 'btc':
                price_in_usd = get_cached_crypto_price('btc', lambda: fetch_crypto_price_with_retry('BTC'))
            elif acc_currency == 'eth':
                price_in_usd = get_cached_crypto_price('eth', lambda: fetch_crypto_price_with_retry('ETH'))
            elif acc_currency == 'trx':
                price_in_usd = get_cached_crypto_price('trx', lambda: fetch_crypto_price_with_retry('TRON'))
            elif acc_currency == 'ltc':
                price_in_usd = get_cached_crypto_price('ltc', lambda: fetch_crypto_price_with_retry('LTC'))

            if price_in_usd is None:
                continue


            balance_in_usd = convert_crypto_to_usd(available_balance, acc_currency)

            if balance_in_usd >= total_charges:

                crypto_charges = convert_dollars_to_crypto(total_charges, price_in_usd)
                receiver_account = MainWalletTable.objects.get(currency=account.currency).virtual_account
                payment_response = send_payment(account.account_id, receiver_account, crypto_charges)

                if payment_response.status_code == 200:
                    print(f"Payment successful for call {call_duration.call_id} from account {account.account_id}")
                    payment_reference = payment_response.json().get('reference', 'N/A')
                    UserTransactionLogs.objects.create(
                        user_id=user,
                        reference=payment_reference,
                        transaction_type=TransactionType.Overage,
                    )
                    call_duration.charged = True
                    call_duration.save()
                    break

                else:
                    print(f"Failed to send payment for call {call_duration.call_id} due to {payment_response.text}")

@shared_task()
def notify_users():
    print("Notifying users.....")

    call_records_paid = CallDuration.objects.filter(notified=False, charged=True)
    users_with_paid_minutes = call_records_paid.values('user_id').annotate(total_paid_minutes=Sum('additional_minutes'))

    call_records_unpaid = CallDuration.objects.filter(notified=False, charged=False)
    users_with_unpaid_minutes = call_records_unpaid.values('user_id').annotate(
        total_unpaid_minutes=Sum('additional_minutes'))

    for user in users_with_paid_minutes:
        user_id = user['user_id']
        paid_minutes = user['total_paid_minutes']
        bot.send_message(user_id, f"Your payment has been successful for {paid_minutes:.4f} additional minutes.")

        CallDuration.objects.filter(user_id=user_id, charged=True, notified=False).update(notified=True)

    for user in users_with_unpaid_minutes:
        user_id = user['user_id']
        unpaid_minutes = user['total_unpaid_minutes']
        bot.send_message(user_id, f"You have insufficient balance to pay {unpaid_minutes:.4f} additional minutes. "
                                  f"Please top up your wallet.")


