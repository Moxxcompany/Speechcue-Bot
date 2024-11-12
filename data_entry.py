import os
from dotenv.main import load_dotenv

load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TelegramBot.settings')  # Replace with your actual settings module
import django
django.setup()

from payment.models import SubscriptionPlans, MainWalletTable

def read_wallet_data(file_path):
    wallet_data = []
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            parts = line.split('|')
            if len(parts) == 5:
                parts.insert(3, '')
            wallet_data.append({
                "xpub": parts[0],
                "mnemonic": parts[1],
                "address": parts[2],
                "virtual_account": parts[3],
                "currency": parts[4],
                "deposit_address": parts[5]
            })
    return wallet_data


def read_subscription_plans(file_path):
    subscription_data = []
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            parts = line.split('|')

            # Check if single_ivr_minutes is provided or not
            single_ivr_minutes = parts[6] if len(parts) > 6 and parts[6] != '' else None

            subscription_data.append({
                "name": parts[0],
                "plan_price": float(parts[1]),
                "number_of_bulk_call_minutes": int(parts[2]),
                "call_transfer": parts[3].lower() == 'true',  # Convert string 'True'/'False' to boolean
                "customer_support_level": parts[4],
                "validity_days": int(parts[5]),
                "single_ivr_minutes": single_ivr_minutes
            })
    return subscription_data


# File paths
wallet_file_path = 'data_files/main_wallet_data.txt'
subscription_file_path = 'data_files/subscription_plans_data.txt'

# Read data from files
wallet_data = read_wallet_data(wallet_file_path)
subscription_data = read_subscription_plans(subscription_file_path)

# Insert subscription plan data using Django ORM
for plan in subscription_data:
    if plan['single_ivr_minutes'] is None:
        SubscriptionPlans.objects.create(
            name=plan['name'],
            plan_price=plan['plan_price'],
            number_of_bulk_call_minutes=plan['number_of_bulk_call_minutes'],
            call_transfer=plan['call_transfer'],
            customer_support_level=plan['customer_support_level'],
            validity_days=plan['validity_days']
        )
    else:
        SubscriptionPlans.objects.create(
            name=plan['name'],
            plan_price=plan['plan_price'],
            number_of_bulk_call_minutes=plan['number_of_bulk_call_minutes'],
            call_transfer=plan['call_transfer'],
            customer_support_level=plan['customer_support_level'],
            validity_days=plan['validity_days'],
            single_ivr_minutes=float(plan['single_ivr_minutes'])
        )

for wallet in wallet_data:
    MainWalletTable.objects.create(
        xpub=wallet['xpub'],
        mnemonic=wallet['mnemonic'],
        address=wallet['address'],
        virtual_account=wallet['virtual_account'],
        currency=wallet['currency'],
        deposit_address=wallet['deposit_address'],
        subscription_id=None,
        private_key=None
    )
