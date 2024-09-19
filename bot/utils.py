import json
from io import BytesIO
import qrcode
from django.core.exceptions import ObjectDoesNotExist
import os
import requests
from payment.models import MainWalletTable, VirtualAccountsTable, SubscriptionPlans, UserSubscription
from payment.views import create_virtual_account, create_deposit_address, get_account_balance
from user.models import TelegramUser
from datetime import timedelta
from django.utils import timezone
from functools import wraps
from bot.bot_config import *
crypto_conversion_base_url = os.getenv('crypto_conversion_base_url')
import random
import string

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
    print("currency : ", )
    wallet = MainWalletTable.objects.get(currency=currency)
    xpub = wallet.xpub
    virtual_account = create_virtual_account(xpub, currency)
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
    balance = get_account_balance(account_id)
    if balance.status_code != 200:
        return f"{balance.json()}"
    balance_data = balance.json()
    available_balance = balance_data["availableBalance"]
    return f"{available_balance}"


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

    # Update or create the user's subscription
    user_subscription, created = UserSubscription.objects.update_or_create(
        user_id=user,
        defaults={
            'subscription_status': 'active',
            'plan_id': plan,
            'transfer_minutes_left': plan.minutes_of_call_transfer,
            'bulk_ivr_calls_left': plan.number_of_calls,
            'date_of_subscription': date_of_subscription,
            'date_of_expiry': date_of_expiry
        }
    )

    return '200'


def get_btc_price():
    url = f"{crypto_conversion_base_url}"
    params = {
        'ids': 'bitcoin',
        'vs_currencies': 'usd'
    }
    response = requests.get(url, params=params)
    data = response.json()
    return float(data['bitcoin']['usd'])

def get_eth_price():
    url = f"{crypto_conversion_base_url}"
    params = {
        'ids': 'ethereum',
        'vs_currencies': 'usd'
    }
    response = requests.get(url, params=params)
    data = response.json()
    return float(data['ethereum']['usd'])

def get_trx_price():
    url = f"{crypto_conversion_base_url}"
    params = {
        'ids': 'tron',
        'vs_currencies': 'usd'
    }
    response = requests.get(url, params=params)
    data = response.json()
    return float(data['tron']['usd'])

def get_ltc_price():
    url = f"{crypto_conversion_base_url}"
    params = {
        'ids': 'litecoin',
        'vs_currencies': 'usd'
    }
    response = requests.get(url, params=params)
    data = response.json()
    return float(data['litecoin']['usd'])

def convert_dollars_to_crypto(amount_in_usd, price_in_usd):
    return float(amount_in_usd) / float(price_in_usd)

def get_plan_price(payment_currency, plan_price):
    if payment_currency == 'BTC':
        btc_price = get_btc_price()
        plan_price = convert_dollars_to_crypto(plan_price, btc_price)

    elif payment_currency == 'ETH':

        eth_price = get_eth_price()
        plan_price = convert_dollars_to_crypto(plan_price, eth_price)

    elif payment_currency == 'TRC':
        tron_price = get_trx_price()
        plan_price = convert_dollars_to_crypto(plan_price, tron_price)

    elif payment_currency == 'LTC':
        ltc_price = get_ltc_price()
        plan_price = convert_dollars_to_crypto(plan_price, ltc_price)

    return plan_price

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

