import json
from http.client import responses
from io import BytesIO
from locale import currency
from logging import exception

import qrcode
import requests

from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse

from TelegramBot.crypto_cache import *
from bot.models import CallLogsTable, CallDuration, BatchCallLogs
from TelegramBot.constants import BTC, ETH, LTC, TRON, MAX_INFINITY_CONSTANT, error


from payment.models import MainWalletTable, VirtualAccountsTable, SubscriptionPlans, UserSubscription, \
    OveragePricingTable, UserTransactionLogs, TransactionType
from payment.views import create_virtual_account, create_deposit_address, get_account_balance, send_payment
from user.models import TelegramUser
from datetime import timedelta
from django.utils import timezone
from functools import wraps
from bot.bot_config import *
crypto_conversion_base_url = os.getenv('crypto_conversion_base_url')
import random
import string
import re
import time
valid_phone_number_pattern = re.compile(r'^[\d\+\-\(\)\s]+$')

def validate_edges(data):
    nodes = data['nodes']
    edges = data['edges']

    source_ids = {edge['source'] for edge in edges}
    target_ids = {edge['target'] for edge in edges}
    missing_sources = []
    missing_targets = []

    for node in nodes:
        node_id = node['id']
        node_name = node['data']['name']
        node_type = node['type']
        node_data = node['data']

        if node_type == 'End Call':
            if node_id not in target_ids:
                missing_targets.append(node_name)

        elif node_data.get('isStart', False):
            if node_id not in source_ids:
                missing_sources.append(node_name)

        else:
            if node_id not in source_ids:
                missing_sources.append(node_name)

            if node_id not in target_ids:
                missing_targets.append(node_name)

    # Handle missing sources and targets
    if missing_sources or missing_targets:
        return {
            'missing_sources': missing_sources,
            'missing_targets': missing_targets,
            'valid': False
        }

    return {
            'missing_sources': None,
            'missing_targets': None,
            'valid': True
        }

def validate_transfer_number(number):
    pattern = r'^\+\d{1,3}\d{7,15}$'
    return re.match(pattern, number) is not None


def add_node(data, new_node):
    data = json.loads(data)
    nodes = data['pathway_data'].get('nodes', [])
    nodes.append(new_node)
    return nodes

def generate_random_id(length=20):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_pathway_data(data):
    if data:
        data = json.loads(data)
        name = data["pathway_data"].get("name")
        description = data["pathway_data"].get("description")
        return name, description
    else:
        return None, None


def get_pathway_payload(data):
    data = json.loads(data)
    payload = data.get("pathway_data")
    return payload

def update_main_wallet_table(user, data, address):
    response_data = json.loads(data)

    account_id = response_data['id']
    account_balance = response_data['balance']['accountBalance']
    available_balance = response_data['balance']['availableBalance']
    currency = response_data['currency']
    frozen = response_data['frozen']
    active = response_data['active']
    customer_id = response_data['customerId']
    account_number = response_data['accountNumber']
    account_code = response_data['accountCode']
    accounting_currency = response_data['accountingCurrency']
    xpub = response_data['xpub']
    account_balance = float(account_balance)
    available_balance = float(available_balance)

    print("Account ID:", account_id)
    print("Account Balance:", account_balance)
    print("Available Balance:", available_balance)


    print("Currency:", currency)
    print("Frozen:", frozen)
    print("Active:", active)
    print("Customer ID:", customer_id)
    print("Account Number:", account_number)
    print("Account Code:", account_code)
    print("Accounting Currency:", accounting_currency)
    print("xpub:", xpub)

def generate_qr_code(address):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(address)
    qr.make(fit=True)

    # Create an image from the QR code
    img = qr.make_image(fill_color="black", back_color="white")

    # Save the image to a BytesIO object
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return img_byte_arr

def create_user_virtual_account(currency, existing_user):
    print("currency : ", currency)
    wallet = MainWalletTable.objects.get(currency=currency)
    xpub = wallet.xpub
    print(f'xpub : {xpub}')
    print(f'userrr id : {existing_user.user_id}')
    virtual_account = create_virtual_account(xpub, currency, existing_user.user_id)
    if virtual_account.status_code != 200:
        return f"Error Creating Virtual Account: {virtual_account.json()}"
    data = virtual_account.json()
    account_id = data['id']
    balance = data['balance']['availableBalance']
    deposit_address = create_deposit_address(account_id)
    if deposit_address.status_code != 200:
        return f"Error Creating Deposit Address: {deposit_address.json()}"
    deposit_data= deposit_address.json()
    address = deposit_data['address']
    main_wallet_address = create_deposit_address(wallet.virtual_account)
    if main_wallet_address.status_code != 200:
        return f"Error Creating Deposit Address: {main_wallet_address.json()}"
    main_wallet_address_data = main_wallet_address.json()
    main_address = main_wallet_address_data['address']
    print(main_wallet_address_data)
    print(main_address)

    try:
        VirtualAccountsTable.objects.create(
            user=existing_user,
            balance=float(balance),
            currency=currency,
            account_detail=json.dumps(virtual_account.json()),
            account_id=account_id,
            deposit_address=address,
            main_wallet_deposit_address=main_address
        )
        return '200'
    except Exception as e:
        return "Error Creating virtual account entry in database!"

def check_balance(account_id):
    try:
        balance = get_account_balance(account_id)
        if balance.status_code != 200:
            # Log or display the full response if the status code is not 200
            raise ValueError(f"Failed to fetch balance. Status Code: {balance.status_code}, Response: {balance.json()}")

        balance_data = balance.json()

        # Ensure 'availableBalance' exists in the response
        if "availableBalance" not in balance_data:
            raise KeyError(f"'availableBalance' key not found in balance response: {balance_data}")

        available_balance = balance_data["availableBalance"]
        return f"{available_balance}"

    except Exception as e:
        # If any exception occurs, log or display the error for debugging
        return f"Error fetching balance: {str(e)}"




def set_user_subscription(user, plan_id):
    try:
        # Fetch the subscription plan based on the plan_id
        plan = SubscriptionPlans.objects.get(plan_id=plan_id)
    except ObjectDoesNotExist:
        return f"Error: Subscription plan with ID {plan_id} does not exist."

    # Get the current date
    date_of_subscription = timezone.now().date()
    try:
        validity_days = int(plan.validity_days)
    except (ValueError, TypeError):
        return "Error: Invalid validity_days in the subscription plan."

    # Calculate the date_of_expiry by adding the validity_days to the subscription date
    date_of_expiry = date_of_subscription + timedelta(days=validity_days)


    user_subscription, created = UserSubscription.objects.update_or_create(
        user_id=user,
        defaults={
            'subscription_status': 'active',
            'plan_id': plan,
            'call_transfer': plan.call_transfer,
            'bulk_ivr_calls_left': plan.number_of_bulk_call_minutes,
            'date_of_subscription': date_of_subscription,
            'date_of_expiry': date_of_expiry,
            'single_ivr_left': plan.single_ivr_minutes
        }
    )

    return '200'

# Cache system for cryptocurrency prices
price_cache = {
    'btc': {'price': None, 'timestamp': 0},
    'eth': {'price': None, 'timestamp': 0},
    'usdt': {'price': None, 'timestamp': 0},
    'ltc': {'price': None, 'timestamp': 0}
}

CACHE_DURATION = 60  # Cache duration in seconds
TATUM_API_URL = os.getenv("TATUM_API_URL")
TATUM_API_KEY = os.getenv("x-api-key")

headers = {
    "accept": "application/json",
    "x-api-key": TATUM_API_KEY
}

# Get cached prices
def get_cached_price(crypto_type, fetch_price_function):
    current_time = time.time()

    if current_time - price_cache[crypto_type]['timestamp'] < CACHE_DURATION:
        return price_cache[crypto_type]['price']

    price = fetch_price_function()
    price_cache[crypto_type]['price'] = price
    price_cache[crypto_type]['timestamp'] = current_time

    return price

# Fetch crypto price from Tatum API
def fetch_crypto_price_from_tatum(crypto_symbol, base_pair='USD'):
    print(f"crypto symbol: {crypto_symbol}")
    print(f"base_pair: {base_pair}")
    url = f"{TATUM_API_URL}/{crypto_symbol.upper()}?basePair={base_pair.upper()}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        print(f"data: {data}")
        if 'value' in data:
            print(f'{float(data["value"])}')
            return float(data['value'])

        else:
            raise ValueError(f"Price not found for {crypto_symbol} in {base_pair}.")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error fetching price for {crypto_symbol}: {str(e)}")

# Fetch individual prices
def get_btc_price():
    return fetch_crypto_price_from_tatum('BTC')

def get_eth_price():
    return fetch_crypto_price_from_tatum('ETH')

def get_usdt_price():  # Updated function for USDT
    return fetch_crypto_price_from_tatum('USDT')

def get_ltc_price():
    return fetch_crypto_price_from_tatum('LTC')

# Convert crypto to USD
def convert_crypto_to_usd(crypto_amount, crypto_type):
    print(f'crypto amount {crypto_amount} and type {crypto_type}')
    try:
        if crypto_type.lower() == 'btc':
            price_in_usd = get_cached_price('btc', get_btc_price)
        elif crypto_type.lower() == 'eth':
            price_in_usd = get_cached_price('eth', get_eth_price)
        elif crypto_type.lower() == 'usdt':
            price_in_usd = get_cached_price('usdt', get_usdt_price)
        elif crypto_type.lower() == 'ltc':
            price_in_usd = get_cached_price('ltc', get_ltc_price)
        else:
            raise ValueError(f"Unsupported cryptocurrency type: {crypto_type}")

        if price_in_usd <= 0:
            raise ValueError(f"Invalid price for {crypto_type}: {price_in_usd}")

        return crypto_amount * price_in_usd

    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error converting {crypto_type} to USD: {str(e)}")

# Convert USD to cryptocurrency
def convert_dollars_to_crypto(amount_in_usd, price_in_usd):
    return float(amount_in_usd) / float(price_in_usd)

# Get the price of a plan in cryptocurrency
def get_plan_price(payment_currency, plan_price):
    if payment_currency.upper() == 'BTC':
        btc_price = get_cached_price('btc', get_btc_price)
        plan_price = convert_dollars_to_crypto(plan_price, btc_price)

    elif payment_currency.upper() == 'ETH':
        eth_price = get_cached_price('eth', get_eth_price)
        plan_price = convert_dollars_to_crypto(plan_price, eth_price)

    elif payment_currency.upper() == 'ERC_20' or payment_currency.upper() == 'TRC_20':
        token_price = get_cached_price('trx', get_usdt_price)
        plan_price = convert_dollars_to_crypto(plan_price, token_price)

    elif payment_currency.upper() == 'LTC':
        ltc_price = get_cached_price('ltc', get_ltc_price)
        plan_price = convert_dollars_to_crypto(plan_price, ltc_price)

    return plan_price

def username_formating(username):
    username = username.lower()
    print("username after converting to lower case ", username)
    username = username.replace(" ", "_")
    print("After replacing spaces ",username)
    return username

def get_currency_symbol(currency):

    if currency == f"{BTC}":
        return '₿'
    if currency == f"{ETH}":
        return 'Ξ'
    if currency == f"{LTC}":
        return 'Ł'
    if currency == f"ERC_20" or currency == f"TRC_20":
        return '💵'


#-------------- Decorator Functions ---------------#

def check_subscription_status(func):
    @wraps(func)
    def wrapper(call, *args, **kwargs):
        user_id = call.message.chat.id

        if check_expiry_date(user_id):
            return func(call, *args, **kwargs)
        else:
            change_subscription_status(user_id)
            bot.send_message(user_id, "Please check your subscription status! "
                                      "You're currently not subscribed to any plan!")
            return None
    return wrapper

def change_subscription_status(user_id):
    try:
        subscription = UserSubscription.objects.get(user_id__user_id=user_id)
        if subscription.subscription_status != 'inactive':
            subscription.subscription_status = 'inactive'
            subscription.save()
    except UserSubscription.DoesNotExist:
        pass
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        if user.subscription_status != 'inactive':
            user.subscription_status = 'inactive'
            user.save()
    except TelegramUser.DoesNotExist:
        pass


def check_validity(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.chat.id

        if check_expiry_date(user_id):
            return func(message, *args, **kwargs)
        else:
            change_subscription_status(user_id)
            bot.send_message(user_id, "Please check your subscription status! "
                                      "You're currently not subscribed to any plan!")
            return None

    return wrapper

def check_expiry_date(user_id):
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        user_subscription = UserSubscription.objects.get(user_id=user)
    except TelegramUser.DoesNotExist:
        return False
    except UserSubscription.DoesNotExist:
        return False

    current_date = timezone.now().date()
    print(current_date, " ", user_subscription.date_of_expiry)
    return user_subscription.date_of_expiry and current_date < user_subscription.date_of_expiry

#--------------------------------------------------#


def get_user_subscription_by_call_id(call_id):
    try:
        try:
            call_log = CallLogsTable.objects.get(call_id=call_id)
            user_id = call_log.user_id
        except CallLogsTable.DoesNotExist:
            return {"status": f"No call log found with call_id {call_id}", "user_subscription": None}

        try:
            user_subscription = UserSubscription.objects.get(user_id=user_id)
        except UserSubscription.DoesNotExist:
            return {"status": f"No user subscription found for user_id {user_id}", "user_subscription": None}

        return {"status": "Success", "user_subscription": user_subscription, "user_id" : user_id}

    except Exception as e:
        return {"status": f"An error occurred: {str(e)}", "user_subscription": None, "user_id" : None}

def charge_additional_mins(user_id, currency, available_balance):
    print("in charge function")
    calls_with_additional_minutes = CallDuration.objects.filter(additional_minutes__gt=0, charged=False, user_id=user_id)

    if calls_with_additional_minutes.exists():
        print("found calls with additional minutes")
        currency = currency
        account = VirtualAccountsTable.objects.get(user_id=user_id, currency=currency)
        account_id = account.account_id
        acc_currency = currency.lower()


        price_in_usd = None
        if acc_currency == 'btc':
            price_in_usd = get_cached_crypto_price('btc', lambda: fetch_crypto_price_with_retry('BTC'))
        elif acc_currency == 'eth':
            price_in_usd = get_cached_crypto_price('eth', lambda: fetch_crypto_price_with_retry('ETH'))
        elif acc_currency == 'erc_20' or acc_currency == 'trc_20':
            price_in_usd = get_cached_crypto_price('usdt', lambda: fetch_crypto_price_with_retry('USDT'))
        elif acc_currency == 'ltc':
            price_in_usd = get_cached_crypto_price('ltc', lambda: fetch_crypto_price_with_retry('LTC'))

        balance_in_usd = convert_crypto_to_usd(available_balance, acc_currency)
        print("balance in usd calculated", balance_in_usd)

        overage_pricing = OveragePricingTable.objects.get(pricing_unit='MIN')
        price_per_min = float(overage_pricing.overage_pricing)
        user = TelegramUser.objects.get(user_id=user_id)
        for call in calls_with_additional_minutes:
            print("in call loop")
            total_charges = price_per_min *  call.additional_minutes
            if balance_in_usd >= total_charges:
                print("balance is sufficient for payment.")

                crypto_charges = convert_dollars_to_crypto(total_charges, price_in_usd)
                receiver_account = MainWalletTable.objects.get(currency=account.currency).virtual_account
                payment_response = send_payment(account_id, receiver_account, crypto_charges)

                if payment_response.status_code == 200:
                    payment_reference = payment_response.json().get('reference', 'N/A')

                    UserTransactionLogs.objects.create(
                        user_id=user,
                        reference=payment_reference,
                        transaction_type=TransactionType.Overage,
                    )
                    call.charged = True
                    call.save()

                else:
                    bot.send_message(user_id,f'Unable to process payment due to the following error: {payment_response.text}')
                return
    return



def get_batch_id(data):
    data = json.loads(data)
    batch_id = data['data']['batch_id']
    return batch_id