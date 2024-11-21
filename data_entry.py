import os
from dotenv.main import load_dotenv

load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TelegramBot.settings')  # Replace with your actual settings module
import django
django.setup()

from payment.models import SubscriptionPlans


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

subscription_file_path = 'data_files/subscription_plans_data.txt'
subscription_data = read_subscription_plans(subscription_file_path)

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

