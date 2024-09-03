import json
from io import BytesIO
import qrcode

from payment.models import MainWalletTable, VirtualAccountsTable
from payment.views import create_virtual_account, create_deposit_address, get_account_balance


def add_node(data, new_node):
    data = json.loads(data)
    nodes = data['pathway_data'].get('nodes', [])
    nodes.append(new_node)
    return nodes

def generate_random_id(length=20):
    """Generates a random ID with a given length"""
    import random
    import string
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
