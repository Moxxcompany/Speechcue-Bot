import json
import os
from locale import currency

from django.http import JsonResponse
from django.shortcuts import render
import requests
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

from TelegramBot import settings
from payment.models import MainWalletTable, OwnerWalletTable

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
    print("account id ", account_id)
    print("webhook ", webhook)
    payload = {
            "type": "ACCOUNT_INCOMING_BLOCKCHAIN_TRANSACTION",
            "attr": {
                "id": f"{account_id}",
                "url": f"{webhook}"
            }
    }

    print(f" x api {x_api_key}")
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response)
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


def stop_single_active_call(call_id):

    url = f"https://api.bland.ai/v1/calls/{call_id}/stop"
    headers = {'authorization': f'{settings.BLAND_API_KEY}'}
    response = requests.request("POST", url, headers=headers)
    print(response.text)

    return response

#--------- Sending transaction to onchain blockchain addresses -----------

def send_BTC_to_blockchain(amount):


    url = "https://api.tatum.io/v3/offchain/bitcoin/transfer"
    sender = MainWalletTable.objects.get(currency="BTC")
    blockchain_address = OwnerWalletTable.objects.get(currency="BTC").address

    payload = make_payload_with_fee(sender, blockchain_address, amount)
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)
    return response

def send_ETH_to_blockchain(amount):

    url = "https://api.tatum.io/v3/offchain/ethereum/transfer"

    sender = MainWalletTable.objects.get(currency ="ETH")
    blockchain_address = OwnerWalletTable.objects.get(currency="ETH").address

    payload = (sender, blockchain_address, amount)
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)



def send_LTC_to_blockchain(amount):

    url = "https://api.tatum.io/v3/offchain/litecoin/transfer"
    sender = MainWalletTable.objects.get(currency ="LTC")
    blockchain_address = OwnerWalletTable.objects.get(currency="LTC").address

    payload = make_payload_with_fee(sender, blockchain_address, amount)
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)
    return response

def send_TRC_20_to_blockchain(amount):

    url = "https://api.tatum.io/v3/offchain/tron/transfer"
    sender = MainWalletTable.objects.get(currency ="TRON")
    blockchain_address = OwnerWalletTable.objects.get(currency="TRON").address

    payload = {
        "address": f"{blockchain_address}",
        "amount": f"{amount}",
        "fromPrivateKey": f"{sender.private_key}",
        "senderAccountId": f"{sender.virtual_account}",
        "fee": f"{sender.fee}"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)
    return response


def send_ERC_20_to_blockchain(amount):

    url = "https://api.tatum.io/v3/offchain/ethereum/erc20/transfer"
    sender = MainWalletTable.objects.get(currency="ETH")

    blockchain_address = OwnerWalletTable.objects.get(currency="ERC").address

    payload = (sender, blockchain_address, amount)
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": f"{x_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)
    return response

def make_payload_ethereum(sender, blockchain_address, amount):
    payload = {
        "senderAccountId": f"{sender.virtual_account}",
        "address": f"{blockchain_address}",
        "amount": f"{amount}",
        "privateKey": f"{sender.private_key}",
        "gasLimit": f"{sender.gas_limit}",
        "gasPrice": f"{sender.gas_price}",
    }
    return payload

def make_payload_with_fee(sender, blockchain_address, amount):
    payload = {
         "senderAccountId": f"{sender.virtual_account}",
        "address": f"{blockchain_address}",
        "amount": f"{amount}",
        "fee": f"{sender.fee}",
        "mnemonic": f"{sender.mnemonic}",
        "xpub": f"{sender.xpub}"
    }
    return payload
