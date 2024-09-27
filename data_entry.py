import os
import uuid
import psycopg2
from dotenv.main import load_dotenv

load_dotenv()
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
            subscription_data.append({
                "name": parts[0],
                "plan_price": float(parts[1]),
                "number_of_bulk_call_minutes": int(parts[2]),
                "call_transfer": int(parts[3]),
                "customer_support_level": parts[4],
                "validity_days": parts[5]
            })
    return subscription_data

conn = psycopg2.connect(
    dbname=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'),
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT'),
)
cur = conn.cursor()

# File paths
wallet_file_path = 'data_files/main_wallet_data.txt'
subscription_file_path = 'data_files/subscription_plans_data.txt'

# Read data from files
wallet_data = read_wallet_data(wallet_file_path)
subscription_data = read_subscription_plans(subscription_file_path)

for wallet in wallet_data:
    cur.execute("""
        INSERT INTO payment_mainwallettable (xpub, mnemonic, address, virtual_account, currency, deposit_address, subscription_id)
        VALUES (%s, %s, %s, %s, %s, %s, NULL)
    """, (wallet['xpub'], wallet['mnemonic'], wallet['address'], wallet['virtual_account'], wallet['currency'], wallet['deposit_address']))

for plan in subscription_data:
    cur.execute("""
        INSERT INTO payment_subscriptionplans (plan_id, name, plan_price, number_of_bulk_call_minutes, call_transfer, customer_support_level, validity_days)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (str(uuid.uuid4()), plan['name'], plan['plan_price'], plan['number_of_bulk_call_minutes'], plan['call_transfer'], plan['customer_support_level'], plan['validity_days']))

conn.commit()

cur.close()
conn.close()
