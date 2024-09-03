import json
import os
from django.http import JsonResponse
from django.shortcuts import render
import requests
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

x_api_key = os.getenv('x-api-key')


#---------------------  BITCOIN   ----------------------#

#   Generating wallet

def create_wallet_BTC():
    url = "https://api.tatum.io/v3/bitcoin/wallet"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}",

    }

    response = requests.get(url, headers=headers)

    return response

#   Generating wallet address

def generate_wallet_address_BTC(xpub, index):
    url = f"https://api.tatum.io/v3/bitcoin/address/{xpub}/{index}"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}",
    }

    response = requests.get(url, headers=headers)

    print(response.text)

#   Generating private key for BTC address

def generate_private_key_BTC(mnemonic, index):

    url = "https://api.tatum.io/v3/bitcoin/wallet/priv"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}",
    }

    payload = {
        "mnemonic": f"{mnemonic}",
        "index": index
    }
    response = requests.post(url, json=payload, headers=headers)

    print(response.text)


#---------------------  ETHEREUM   ----------------------#

#   Generating wallet

def create_wallet_Ethereum():

    url = "https://api.tatum.io/v3/ethereum/wallet?testnetType=ethereum-sepolia"

    headers = {
        "accept": "application/json",
        "x-testnet-type": "ethereum-sepolia",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.get(url, headers=headers)

    print(response.text)

#   Generate wallet address

def generate_wallet_address_Ethereum(xpub, index):
    url = f"https://api.tatum.io/v3/ethereum/address/{xpub}/{index}"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.get(url, headers=headers)

    print(response.text)

#   Generate private key for wallet address

def generate_private_key_Ethereum(mnemonic, index):
    url = "https://api.tatum.io/v3/ethereum/wallet/priv"

    payload = {
        "index": index,
        "mnemonic": f"{mnemonic}"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)

#---------------------  LITECOIN   ----------------------#

#   Generate a wallet

def create_wallet_Litecoin():
    url = "https://api.tatum.io/v3/litecoin/wallet"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.get(url, headers=headers)

    print(response.text)


def create_wallet_Tron():
    url = "https://api.tatum.io/v3/tron/wallet"
    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.get(url, headers=headers)

    print(response.text)

def generate_wallet_address_Tron(xpub, index):

    url = "https://api.tatum.io/v3/tron/address/xpub/index"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.get(url, headers=headers)

    print(response.text)

def generate_private_key_Tron(mnemonic, index):

    url = "https://api.tatum.io/v3/tron/wallet/priv"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}",
    }

    payload = {
        "mnemonic": f"{mnemonic}",
        "index": index
    }
    response = requests.post(url, json=payload, headers=headers)

    print(response.text)

#---------------------  VIRTUAL ACCOUNTS   ----------------------#

#   Create Account

def create_virtual_account(xpub, currency, customer_external_id=None):

    url = "https://api.tatum.io/v3/ledger/account"

    payload = {
        "currency": f"{currency}",
        "xpub": f"{xpub}"
    }
    if customer_external_id is not None:
        payload["customer"] = {"externalId": f"{customer_external_id}"}

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    return response


#   Create deposit address for the virtual accounts

def create_deposit_address(account_id):

    url = f"https://api.tatum.io/v3/offchain/account/{account_id}/address"

    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, headers=headers)

    return response

# Check Balance

def get_account_balance(account_id):
    url = f"https://api.tatum.io/v3/ledger/account/{account_id}/balance"
    headers = {
        "accept": "application/json",
        "x-api-key": f"{x_api_key}"
    }
    response = requests.get(url, headers=headers)
    print(response)
    return response

def create_subscription_v3(account_id, webhook):
    url = "https://api.tatum.io/v3/subscription"

    payload = {
            "type": "ACCOUNT_INCOMING_BLOCKCHAIN_TRANSACTION",
            "attr": {
                "id": f"{account_id}",
                "url": f"{webhook}"
            }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    return response

#---------------------  PAYMENT  ----------------------#
def send_payment(sender_account, receiver_account, amount):
    url = "https://api.tatum.io/v3/ledger/transaction"

    payload = {
        "anonymous": False,
        "baseRate": 1,
        "amount": f"{amount}",
        "recipientAccountId": f"{receiver_account}",
        "senderAccountId": f"{sender_account}"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response