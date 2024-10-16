import os
from decimal import Decimal
from locale import currency

import requests
from celery import shared_task
from django.core.cache import cache
from .bot_config import *

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from dotenv.main import load_dotenv

from payment.admin import CallDurationAdmin
from payment.models import UserSubscription, VirtualAccountsTable, OveragePricingTable, MainWalletTable, \
    UserTransactionLogs, TransactionType
from user.models import TelegramUser
from .models import CallLogsTable, CallDuration
from payment.views import stop_single_active_call, get_account_balance, send_payment
from .utils import get_user_subscription_by_call_id, convert_crypto_to_usd, convert_dollars_to_crypto, get_btc_price, \
    get_eth_price, get_trx_price, get_ltc_price

# Load environment variables
load_dotenv()

@shared_task
def check_call_status():
    bland_api_key = os.getenv('BLAND_API_KEY')
    print("Starting check_call_status task with API key: ", bland_api_key)

    tracked_calls = CallLogsTable.objects.filter(call_status__in=['new','queued' ,'started'])

    for call in tracked_calls:
        headers = {"authorization": f"{bland_api_key}"}
        response = requests.get(f"https://api.bland.ai/v1/calls/{call.call_id}", headers=headers)
        print(f"Processing call ID: {call.call_id}")

        if response.status_code == 200:
            call_data = response.json()
            queue_status = call_data.get('queue_status', '')
            started_at_str = call_data.get('started_at', None)
            end_at_str = call_data.get('end_at', None)
            call_length = call_data.get('call_length', None)
            print("queue_status: ", queue_status)
            print("started_at_str: ", started_at_str)
            print("end_at_str: ", end_at_str)
            print("call_length: ", call_length)

            started_at = parse_datetime(started_at_str) if started_at_str else None
            end_at = parse_datetime(end_at_str) if end_at_str else None

            subscription_result = get_user_subscription_by_call_id(call.call_id)
            print("subscription_result: ", subscription_result)

            if subscription_result['status'] != 'Success':
                print(subscription_result['status'])
                continue

            user_subscription = subscription_result['user_subscription']
            print("user_subscription: ", user_subscription)
            bulk_ivr_calls_left = user_subscription.bulk_ivr_calls_left

            # If the call status is "started"
            if queue_status == 'started' and started_at:
                print("Call is in progress (started)")

                # Calculate duration from the start time to now
                current_time = timezone.now()
                print("current_time: ", current_time)

                ongoing_duration_seconds = (current_time - started_at).total_seconds()
                print("ongoing_duration_seconds: ", ongoing_duration_seconds)

                ongoing_duration_minutes = ongoing_duration_seconds / 60
                print("ongoing_duration_minutes: ", ongoing_duration_minutes)

                if ongoing_duration_minutes >= bulk_ivr_calls_left:

                    difference = ongoing_duration_minutes - bulk_ivr_calls_left
                    print("difference: ", difference)

                    call_duration_record, created = CallDuration.objects.update_or_create(
                        call_id=call.call_id,
                        pathway_id=call.pathway_id,
                        defaults={
                            'start_time': started_at,
                            'queue_status': queue_status,
                            'duration_in_seconds': ongoing_duration_seconds,
                            'additional_minutes': 0,
                            'user_id': user_subscription['user_id']
                        }
                    )

                    # Terminate the call
                    stop_response = stop_single_active_call(call.call_id)
                    if stop_response.status_code == 200:
                        print(f"Call {call.call_id} has been terminated.")

                        user_subscription.bulk_ivr_calls_left = 0
                        user_subscription.save()

                        # Mark the call as terminated
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
                print("Call is completed")

                duration_in_seconds = (end_at - started_at).total_seconds()
                print("duration_in_seconds: (completed) ", duration_in_seconds)

                duration_in_minutes = duration_in_seconds / 60
                print("duration_in_minutes: (completed) ", duration_in_minutes)

                if duration_in_minutes > bulk_ivr_calls_left:
                    difference = duration_in_minutes - bulk_ivr_calls_left
                    print("difference (completed) : ", difference)

                    call_duration_record, created = CallDuration.objects.update_or_create(
                        call_id=call.call_id,
                        pathway_id=call.pathway_id,
                        defaults={
                            'start_time': started_at,
                            'end_time': end_at,
                            'queue_status': queue_status,
                            'duration_in_seconds': duration_in_seconds,
                            'additional_minutes': f"{difference}",
                            'user_id': user_subscription['user_id']

                        }
                    )

                    user_subscription.bulk_ivr_calls_left = 0
                    user_subscription.save()

                else:
                    duration_in_minutes = Decimal(duration_in_seconds / 60)
                    remaining_minutes = bulk_ivr_calls_left - duration_in_minutes

                    call_duration_record, created = CallDuration.objects.update_or_create(
                        call_id=call.call_id,
                        pathway_id=call.pathway_id,
                        defaults={
                            'start_time': started_at,
                            'end_time': end_at,
                            'queue_status': queue_status,
                            'duration_in_seconds': duration_in_seconds,
                            'additional_minutes': 0,
                            'user_id': user_subscription['user_id']

                        }
                    )

                    # Update the subscription with remaining minutes
                    user_subscription.bulk_ivr_calls_left = remaining_minutes
                    user_subscription.save()

                # Mark the call as completed
                call.call_status = queue_status
                call.save()

        else:
            print(f"Failed to fetch call details for call ID: {call.call_id}. Status Code: {response.status_code}")


# Helper function to cache cryptocurrency prices
def get_cached_crypto_price(crypto_symbol, fetch_func):
    cache_key = f"{crypto_symbol}_price"
    price = cache.get(cache_key)

    if not price:
        # Fetch price using provided function if not in cache
        price = fetch_func()
        # Cache the price for 5 minutes (300 seconds)
        cache.set(cache_key, price, timeout=300)  # Cache for 5 minutes
        print(f"Fetched and cached price for {crypto_symbol}: {price}")
    else:
        print(f"Using cached price for {crypto_symbol}: {price}")

    return price


# Gracefully handle insufficient balance cases
def handle_insufficient_balance(user, account, total_charges):
    # Log the issue or notify the user via an appropriate method (e.g., email, message, etc.)
    print(f"Notifying user {user.user_id} about insufficient balance for charges: {total_charges} USD")
    # Example: Send a message or email to the user
    # send_notification_to_user(user, f"Insufficient balance for account {account.account_id}. Charges: {total_charges} USD")


@shared_task
def charge_user_for_additional_minutes():
    print("Charge_user_for_additional_minutes RUNNING..... ")

    calls_with_additional_minutes = CallDuration.objects.filter(additional_minutes__gt=0, charged=False)

    for call_duration in calls_with_additional_minutes:
        user = TelegramUser.objects.get(user_id=call_duration.user_id)
        account_obj = VirtualAccountsTable.objects.filter(user_id=user)

        for account in account_obj:
            # Fetch account balance
            balance_response = get_account_balance(account.account_id)
            if balance_response.status_code != 200:
                print(f"Failed to fetch account balance due to the following error: {balance_response.text}")
                continue

            balance_data = balance_response.json()
            available_balance = float(balance_data["availableBalance"])
            acc_currency = account.currency.lower()
            print(f"Account currency: {acc_currency}")

            # Convert available balance to USD
            balance_in_usd = convert_crypto_to_usd(available_balance, acc_currency)

            # Get overage pricing per minute
            overage_pricing = OveragePricingTable.objects.get(pricing_unit='MIN')
            price_per_min = float(overage_pricing.overage_pricing)
            total_charges = price_per_min * call_duration.additional_minutes

            # Check if the balance is sufficient
            if balance_in_usd >= total_charges:
                # Use cached crypto price for conversion to USD
                if acc_currency == 'btc':
                    price_in_usd = get_cached_crypto_price('btc', get_btc_price)
                elif acc_currency == 'eth':
                    price_in_usd = get_cached_crypto_price('eth', get_eth_price)
                elif acc_currency in ['trx', 'tron']:
                    price_in_usd = get_cached_crypto_price('trx', get_trx_price)
                elif acc_currency == 'ltc':
                    price_in_usd = get_cached_crypto_price('ltc', get_ltc_price)
                else:
                    raise ValueError(f"Unsupported cryptocurrency type: {acc_currency}")

                # Convert total charges from USD to the cryptocurrency
                crypto_price = convert_dollars_to_crypto(total_charges, price_in_usd)

                # Perform the payment
                receiver_account = MainWalletTable.objects.get(currency=account.currency).virtual_account
                payment_response = send_payment(account.account_id, receiver_account, crypto_price)

                if payment_response.status_code != 200:
                    print(f"Failed to send payment due to the following error: {payment_response.text}")
                    continue

                print("Successfully sent payment")

                payment_reference = payment_response.json().get('reference', 'N/A')

                # Log the transaction in the UserTransactionLogs table
                UserTransactionLogs.objects.create(
                    user_id=user,
                    reference=payment_reference,  # Store the payment reference
                    transaction_type=TransactionType.Overage,  # Using the Overage type here
                )

                # Mark the call duration as charged
                call_duration.charged = True
                call_duration.save()
                break  # Stop processing other accounts for this user since payment is successful

            else:
                # Handle insufficient balance
                print(f"Not enough balance! Charges: {total_charges} USD, Available balance: {balance_in_usd} USD")
                handle_insufficient_balance(user, account, total_charges)
                continue
