import json
import os
from django.core.exceptions import ObjectDoesNotExist
from requests.exceptions import RequestException
import requests
from TelegramBot import settings
from user.models import TelegramUser


#-------------------- Env Variables --------------------

x_api_key = os.getenv('x-api-key')
dynopay_base_url = os.getenv('dynopay_base_url')




#-------------------- USER SIGN UP --------------------


def setup_user(user_id, email, mobile, name, username):
    try:


        url = f"{dynopay_base_url}/user/createUser"
        payload = json.dumps({
            "email": email,
            "name": name,
            "mobile": mobile
        })
        headers = {
            'x-api-key': x_api_key,
            'Content-Type': 'application/json'
        }

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            print(response.text)
            if response.status_code != 200:
                return {"status": response.status_code, "text": response.text}

            data = response.json().get('data', {})
            token = data.get('token')
            customer_id = data.get('customer_id')

            if not token or not customer_id:
                return {"status": 500, "text": "API response did not contain token or customer_id"}

        except RequestException as api_error:
            print("API request encountered an error:", api_error)
            return {"status": 502, "text": f"API request failed: {str(api_error)}"}

        try:
            user = TelegramUser.objects.get(user_id=user_id)
            user.user_name = username
            user.token = token
            user.customer_id = customer_id
            user.save()
            print("User successfully updated in the database.")
            return {"status": 200, "text": "User setup successfully"}

        except ObjectDoesNotExist:
            print(f"No TelegramUser found with user_id: {user_id}")
            return {"status": 404, "text": "User not found in database"}

        except Exception as db_error:
            print("An error occurred while updating the user:", db_error)
            return {"status": 500, "text": f"Database error: {str(db_error)}"}

    except Exception as e:
        print("An unexpected error occurred:", e)
        return {"status": 500, "text": f"An unexpected error occurred: {str(e)}"}

#------------------- Check Balance --------------------

def check_user_balance(user_id):

    url = f"{dynopay_base_url}/user/getBalance"
    token = TelegramUser.objects.get(user_id=user_id).token
    print(f"token : {token}")
    print(f"x-api-key : {x_api_key}")
    payload = {}
    headers = {
        'x-api-key': f'{x_api_key}',
        'Authorization': f'Bearer {token}'
    }
    print("headers : {}".format(headers))

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)

    return response

def create_crypto_payment(user_id, amount, currency, redirect_uri, auto_renewal, top_up=False):
    url = f"{dynopay_base_url}/user/cryptoPayment"

    # Prepare payload with optional meta_data
    payload = json.dumps({
        "amount": float(amount),
        "currency": currency,
        "redirect_uri": redirect_uri,
        "topUp":top_up,
        "meta_data": {
            "product_name": f"{user_id}",
            "product": f"{auto_renewal}"
        }
    })
    print(f"payload : {payload}")
    token = TelegramUser.objects.get(user_id=user_id).token
    headers = {
        'x-api-key': x_api_key,
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    response = requests.post(url, headers=headers, data=payload)
    print(response.text)
    return response


def credit_wallet_balance(user_id, amount):
    token = TelegramUser.objects.get(user_id=user_id).token
    headers = {
        'x-api-key': x_api_key,
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    payload = json.dumps({
        "amount": float(amount)
    })
    print(f"payload : {payload}")

    url = f"{dynopay_base_url}/user/useWallet"
    response = requests.post(url, headers=headers, data=payload)
    print(response.text)
    return response

def get_user_single_transaction(user_id, transaction_id):
    token = TelegramUser.objects.get(user_id=user_id).token
    url = f"{dynopay_base_url}/user/getSingleTransaction/{transaction_id}"

    payload = {}
    headers = {
        'x-api-key': x_api_key,
        'Authorization': f'Bearer {token}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)
    return response

def get_all_user_transactions(user_id):
    token = TelegramUser.objects.get(user_id=user_id).token

    url = f"{dynopay_base_url}/user/getTransactions"

    payload = {}
    headers = {
        'x-api-key': x_api_key,
        'Authorization': f'Bearer {token}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)
    return response