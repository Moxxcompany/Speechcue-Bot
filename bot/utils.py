import importlib
import json

from translations.translations import *
from django.core.exceptions import ObjectDoesNotExist

from TelegramBot import settings
from TelegramBot.crypto_cache import *
from bot.models import CallLogsTable, CallDuration, BatchCallLogs
from TelegramBot.constants import BTC, ETH, LTC, STATUS_CODE_200, ACTIVE
from payment.models import SubscriptionPlans, UserSubscription
from user.models import TelegramUser
from datetime import timedelta
from django.utils import timezone
from bot.bot_config import *

crypto_conversion_base_url = os.getenv("crypto_conversion_base_url")
import random

import time
import redis

import re
import string


def categorize_voices_by_description(data, gender):

    gender = gender.lower()  # Normalize input
    if gender not in ["male", "female"]:
        raise ValueError("Gender must be 'Male' or 'Female'.")

    gender_keywords = {
        "male": [" male", "man", "boy"],
        "female": [" female", "woman", "girl"],
    }

    filtered_voices = [
        voice
        for voice in data
        if "description" in voice
        and voice["description"]
        and any(
            keyword in voice["description"].lower()
            for keyword in gender_keywords[gender]
        )
        and not any(
            keyword in voice["description"].lower()
            for keyword in gender_keywords["male" if gender == "female" else "female"]
        )
    ]
    return filtered_voices


def remove_punctuation_and_spaces(input_string):
    formatted_string = re.sub(
        r"[{}]\s+".format(re.escape(string.punctuation)), "", input_string
    )
    print("in formatting function ", formatted_string)
    return formatted_string


redis_client = redis.StrictRedis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB
)


valid_phone_number_pattern = re.compile(r"^[\d\+\-\(\)\s]+$")


def validate_edges(data):
    nodes = data["nodes"]
    edges = data["edges"]

    source_ids = {edge["source"] for edge in edges}
    target_ids = {edge["target"] for edge in edges}
    missing_sources = []
    missing_targets = []

    for node in nodes:
        node_id = node["id"]
        node_name = node["data"]["name"]
        node_type = node["type"]
        node_data = node["data"]

        if node_type == "End Call":
            # End Call nodes must be referenced as targets
            if node_id not in target_ids:
                missing_targets.append(node_name)

        elif node_type == "Transfer Call":
            # Transfer Call nodes only require incoming edges
            if node_id not in target_ids:
                missing_targets.append(node_name)

        elif node_data.get("isStart", False):
            # Start nodes must be referenced as sources
            if node_id not in source_ids:
                missing_sources.append(node_name)

        else:
            # Other nodes must have both incoming and outgoing edges
            if node_id not in source_ids:
                missing_sources.append(node_name)
            if node_id not in target_ids:
                missing_targets.append(node_name)

    # Handle missing sources and targets
    if missing_sources or missing_targets:
        return {
            "missing_sources": missing_sources,
            "missing_targets": missing_targets,
            "valid": False,
        }

    return {"missing_sources": None, "missing_targets": None, "valid": True}


def validate_transfer_number(number):
    pattern = r"^\+\d{1,3}\d{7,15}$"
    return re.match(pattern, number) is not None


def add_node(data, new_node):
    data = json.loads(data)
    nodes = data["pathway_data"].get("nodes", [])
    nodes.append(new_node)
    return nodes


def generate_random_id(length=20):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


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


def set_user_subscription(user, plan_id):
    try:
        plan = SubscriptionPlans.objects.get(plan_id=plan_id)
    except ObjectDoesNotExist:
        return f"Error: Subscription plan with ID {plan_id} does not exist."

    date_of_subscription = timezone.now().date()
    try:
        validity_days = int(plan.validity_days)
    except (ValueError, TypeError):
        return "Error: Invalid validity_days in the subscription plan."
    date_of_expiry = date_of_subscription + timedelta(days=validity_days)

    user_subscription, created = UserSubscription.objects.update_or_create(
        user_id=user,
        defaults={
            "subscription_status": "active",
            "plan_id": plan,
            "call_transfer": plan.call_transfer,
            "bulk_ivr_calls_left": plan.number_of_bulk_call_minutes,
            "date_of_subscription": date_of_subscription,
            "date_of_expiry": date_of_expiry,
            "single_ivr_left": plan.single_ivr_minutes,
        },
    )
    user.free_plan = False
    user.save()
    return "200"


def set_details_for_user_table(user_id, plan_id):
    try:
        current_user = TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        return {"status": 404, "text": f"User with ID {user_id} does not exist."}
    except Exception as e:
        return {
            "status": 500,
            "text": f"An error occurred while retrieving the user: {str(e)}",
        }

    try:
        current_user.subscription_status = f"{ACTIVE}"
        current_user.plan = plan_id
        current_user.save()
    except Exception as e:
        return {
            "status": 500,
            "message": f"An error occurred while saving the user's subscription status: {str(e)}",
        }
    return {"status": 200, "message": current_user}


def set_plan(user_id, plan_id, auto_renewal):

    response = set_details_for_user_table(user_id, plan_id)
    if response["status"] != 200:
        bot.send_message(user_id, f"{response['message']}")
        return
    current_user = response["message"]

    try:
        set_subscription = set_user_subscription(current_user, plan_id)
        if set_subscription != f"{STATUS_CODE_200}":
            bot.send_message(user_id, set_subscription)
            return {
                "status": 400,
                "message": f"Failed to set user subscription: {set_subscription}",
            }
    except Exception as e:
        return {
            "status": 500,
            "message": f"An error occurred in set_user_subscription: {str(e)}",
        }

    try:
        print(f"set plan auto renewal {auto_renewal}")
        user_subscription, created = UserSubscription.objects.get_or_create(
            user_id=current_user
        )
        user_subscription.auto_renewal = auto_renewal
        user_subscription.save()
    except Exception as e:
        return {
            "status": 500,
            "message": f"An error occurred while saving the auto-renewal setting: {str(e)}",
        }

    return {"status": 200, "message": "Subscription plan updated successfully."}


price_cache = {
    "btc": {"price": None, "timestamp": 0},
    "eth": {"price": None, "timestamp": 0},
    "usdt_erc20": {"price": None, "timestamp": 0},
    "usdt_trc20": {"price": None, "timestamp": 0},
    "ltc": {"price": None, "timestamp": 0},
    "bch": {"price": None, "timestamp": 0},
    "doge": {"price": None, "timestamp": 0},
    "trx": {"price": None, "timestamp": 0},
}

CACHE_DURATION = 60
TATUM_API_URL = os.getenv("TATUM_API_URL")
TATUM_API_KEY = os.getenv("x_api_tatum")

headers = {"accept": "application/json", "x-api-key": TATUM_API_KEY}


def get_cached_price(crypto_type, fetch_price_function):
    current_time = time.time()
    if current_time - price_cache[crypto_type]["timestamp"] < CACHE_DURATION:
        return price_cache[crypto_type]["price"]

    price = fetch_price_function()
    price_cache[crypto_type]["price"] = price
    price_cache[crypto_type]["timestamp"] = current_time
    return price


def fetch_crypto_price_from_tatum(crypto_symbol, base_pair="USD"):
    if crypto_symbol == "USDT-ERC20":
        url = f"{TATUM_API_URL}/USDT?basePair={base_pair.upper()}"
    elif crypto_symbol == "USDT-TRC20":
        url = f"{TATUM_API_URL}/USDT_TRON?basePair={base_pair.upper()}"
    else:
        url = f"{TATUM_API_URL}/{crypto_symbol.upper()}?basePair={base_pair.upper()}"
    try:
        print(f"url: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "value" in data:
            return float(data["value"])
        else:
            raise ValueError(f"Price not found for {crypto_symbol} in {base_pair}.")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error fetching price for {crypto_symbol}: {str(e)}")


def get_btc_price():
    return fetch_crypto_price_from_tatum("BTC")


def get_eth_price():
    return fetch_crypto_price_from_tatum("ETH")


def get_usdt_erc20_price():
    return fetch_crypto_price_from_tatum("USDT-ERC20")


def get_usdt_trc20_price():
    return fetch_crypto_price_from_tatum("USDT-TRC20")


def get_ltc_price():
    return fetch_crypto_price_from_tatum("LTC")


def get_bch_price():
    return fetch_crypto_price_from_tatum("BCH")


def get_doge_price():
    return fetch_crypto_price_from_tatum("DOGE")


def get_trx_price():
    return fetch_crypto_price_from_tatum("TRX")


def convert_crypto_to_usd(crypto_amount, crypto_type):
    try:
        if crypto_type.lower() == "btc":
            price_in_usd = get_cached_price("btc", get_btc_price)
        elif crypto_type.lower() == "eth":
            price_in_usd = get_cached_price("eth", get_eth_price)
        elif crypto_type.lower() == "usdt-erc20":
            price_in_usd = get_cached_price("usdt_erc20", get_usdt_erc20_price)
        elif crypto_type.lower() == "usdt-trc20":
            price_in_usd = get_cached_price("usdt_trc20", get_usdt_trc20_price)
        elif crypto_type.lower() == "ltc":
            price_in_usd = get_cached_price("ltc", get_ltc_price)
        elif crypto_type.lower() == "bch":
            price_in_usd = get_cached_price("bch", get_bch_price)
        elif crypto_type.lower() == "doge":
            price_in_usd = get_cached_price("doge", get_doge_price)
        elif crypto_type.lower() == "trx":
            price_in_usd = get_cached_price("trx", get_trx_price)
        else:
            raise ValueError(f"Unsupported cryptocurrency type: {crypto_type}")
        if price_in_usd <= 0:
            raise ValueError(f"Invalid price for {crypto_type}: {price_in_usd}")

        return crypto_amount * price_in_usd

    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error converting {crypto_type} to USD: {str(e)}")


def convert_dollars_to_crypto(amount_in_usd, price_in_usd):
    return float(amount_in_usd) / float(price_in_usd)


def get_plan_price(payment_currency, plan_price):
    if payment_currency.upper() == "BTC":
        btc_price = get_cached_price("btc", get_btc_price)
        plan_price = convert_dollars_to_crypto(plan_price, btc_price)

    elif payment_currency.upper() == "ETH":
        eth_price = get_cached_price("eth", get_eth_price)
        plan_price = convert_dollars_to_crypto(plan_price, eth_price)

    elif payment_currency.upper() == "USDT-ERC20":
        usdt_erc20_price = get_cached_price("usdt_erc20", get_usdt_erc20_price)
        plan_price = convert_dollars_to_crypto(plan_price, usdt_erc20_price)

    elif payment_currency.upper() == "USDT-TRC20":
        usdt_trc20_price = get_cached_price("usdt_trc20", get_usdt_trc20_price)
        plan_price = convert_dollars_to_crypto(plan_price, usdt_trc20_price)

    elif payment_currency.upper() == "LTC":
        ltc_price = get_cached_price("ltc", get_ltc_price)
        plan_price = convert_dollars_to_crypto(plan_price, ltc_price)

    elif payment_currency.upper() == "BCH":
        bch_price = get_cached_price("bch", get_bch_price)
        plan_price = convert_dollars_to_crypto(plan_price, bch_price)

    elif payment_currency.upper() == "DOGE":
        doge_price = get_cached_price("doge", get_doge_price)
        plan_price = convert_dollars_to_crypto(plan_price, doge_price)

    elif payment_currency.upper() == "TRX":
        trx_price = get_cached_price("trx", get_trx_price)
        plan_price = convert_dollars_to_crypto(plan_price, trx_price)

    return plan_price


def username_formating(username):
    username = username.lower()
    print("username after converting to lower case ", username)
    username = username.replace(" ", "_")
    print("After replacing spaces ", username)
    return username


# --------------------------------------------------#


def get_user_subscription_by_call_id(call_id):
    try:
        try:
            call_log = CallLogsTable.objects.get(call_id=call_id)
            user_id = call_log.user_id
        except CallLogsTable.DoesNotExist:
            return {
                "status": f"No call log found with call_id {call_id}",
                "user_subscription": None,
            }

        try:
            user_subscription = UserSubscription.objects.get(user_id=user_id)
        except UserSubscription.DoesNotExist:
            return {
                "status": f"No user subscription found for user_id {user_id}",
                "user_subscription": None,
            }

        return {
            "status": "Success",
            "user_subscription": user_subscription,
            "user_id": user_id,
        }

    except Exception as e:
        return {
            "status": f"An error occurred: {str(e)}",
            "user_subscription": None,
            "user_id": None,
        }


def get_batch_id(data):
    data = json.loads(data)
    batch_id = data["data"]["batch_id"]
    return batch_id


def get_currency(payment_method):
    mapping = {
        "Bitcoin (BTC) ₿": f"{BTC}",
        "比特币 (BTC) ₿": f"{BTC}",
        "Ethereum (ETH) Ξ": f"{ETH}",
        "以太坊 (ETH) Ξ": f"{ETH}",
        "TRC-20 USDT 💵": "USDT-TRC20",
        "TRC-20 USDT 💵": "USDT-TRC20",
        "ERC-20 USDT 💵": "USDT-ERC20",
        "ERC-20 USDT 💵": "USDT-ERC20",
        "Litecoin (LTC) Ł": f"{LTC}",
        "莱特币 (LTC) Ł": f"{LTC}",
        "DOGE (DOGE) Ɖ": "DOGE",
        "狗狗币 (DOGE) Ɖ": "DOGE",
        "Bitcoin Hash (BCH) Ƀ": "BCH",
        "比特币现金 (BCH) Ƀ": "BCH",
        "TRON (TRX)": "TRX",
        "波场 (TRX)": "TRX",
    }
    payment_currency = mapping.get(payment_method, "Unsupported")
    if payment_currency == "Unsupported":
        status = 400
    else:
        status = 200
    print(payment_currency)
    return {"status": status, "text": payment_currency}


def get_user_language(user_id):
    cached_language = redis_client.get(f"user_language:{user_id}")
    print(f"for user id : {user_id}")
    if cached_language:
        lg = cached_language.decode("utf-8")
        print(f"Returning cached language: {lg}")
        return lg
    else:
        language = TelegramUser.objects.get(user_id=user_id).language
        print(f"Returning language from database: {language}")
        redis_client.set(f"user_language:{user_id}", language)

        return language


def reset_user_language(user_id):
    redis_client.delete(f"user_language:{user_id}")
