import uuid

from django.db import models

from TelegramBot.constants import MAX_INFINITY_CONSTANT
from user.models import TelegramUser


class SubscriptionPlans(models.Model):

    plan_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    plan_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    number_of_bulk_call_minutes = models.DecimalField(null=True, max_digits=20, decimal_places=6, blank=True)
    call_transfer = models.BooleanField(default=False)
    customer_support_level = models.TextField(max_length=100)
    validity_days = models.IntegerField( blank=True, null=True)
    single_ivr_minutes = models.DecimalField(max_digits=20, decimal_places=6 ,default=MAX_INFINITY_CONSTANT)


    def __str__(self):
        return self.name

class MainWalletTable(models.Model):
    xpub = models.TextField(primary_key=True)
    mnemonic = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    virtual_account = models.TextField(null=True, blank=True)
    currency = models.TextField(null=True, blank=True)
    deposit_address = models.TextField(null=True, blank=True)
    subscription_id = models.CharField(max_length=100, null=True, blank=True)
    private_key = models.TextField(null=True, blank=True)
    fee = models.DecimalField(max_digits=20, decimal_places=6, default=0.00001)
    gas_price = models.CharField(max_length=100, default='20')
    gas_limit = models.CharField(max_length=100, default='40000')

    def __str__(self):
        return self.address

class VirtualAccountsTable(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='user_accounts')
    balance = models.DecimalField(max_digits=10, decimal_places=8, default=0.00000000)
    currency = models.TextField(null=True, blank=True)
    account_detail = models.TextField(null=True, blank=True)
    account_id = models.TextField(primary_key=True)
    deposit_address = models.TextField(null=True, blank=True)
    subscription_id = models.CharField(max_length=100, null=True, blank=True)
    main_wallet_deposit_address = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.account_id


class UserSubscription(models.Model):
    user_id = models.ForeignKey(TelegramUser, on_delete= models.DO_NOTHING,related_name='subscription_user_id')
    subscription_status = models.CharField(max_length=50, null=True, default='inactive')
    plan_id = models.ForeignKey(SubscriptionPlans, on_delete=models.CASCADE, related_name='subscription_user_plan')
    bulk_ivr_calls_left = models.DecimalField(null=True, max_digits=20, decimal_places=6, blank=True)
    date_of_subscription = models.DateField(auto_now_add=True, blank=True, null=True)
    date_of_expiry = models.DateField(null = True, blank=True)
    call_transfer = models.BooleanField(default=False)
    auto_renewal = models.BooleanField(default=False)
    single_ivr_left = models.DecimalField(null=True, max_digits=20, decimal_places=6, blank=True)


class OwnerWalletTable(models.Model):
    address = models.TextField(primary_key=True)
    currency = models.TextField(null=True, blank=True)

class TransactionType(models.TextChoices):
    SUBSCRIPTION = 'SUB', 'Subscription'
    Overage = 'OVR', 'Overage'
    WITHDRAWAL = 'WDR', 'Withdrawal'
    DEPOSIT = 'DEP', 'Deposit'
    TRANSFER = 'TRF', 'Transfer'


class UserTransactionLogs(models.Model):
    transaction_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    user_id = models.CharField(max_length=200, null=True, blank=True)
    reference = models.CharField(max_length=200, null=True, blank=True)
    transaction_type = models.CharField(
        max_length=3,
        choices=TransactionType.choices,
        default=TransactionType.SUBSCRIPTION
    )
    transaction_date = models.DateField(auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return f'{self.get_transaction_type_display()}'

class PricingUnits(models.TextChoices):
    MINUTES = 'MIN', 'Minutes'
    SECONDS = 'SEC', 'Seconds'
    HOURS = 'HRS', 'Hours'

class OveragePricingTable(models.Model):
    overage_pricing = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    pricing_unit = models.CharField(
        max_length=3,
        choices=PricingUnits.choices,
        default=PricingUnits.MINUTES,
        primary_key=True
    )
    def __str__(self):
        return f'{self.pricing_unit}'

class ManageFreePlanSingleIVRCall(models.Model):
    user_id = models.ForeignKey(TelegramUser, on_delete= models.DO_NOTHING, related_name='manage_free_plans')
    call_duration = models.DecimalField(max_digits=20, decimal_places=6,default=0)
    call_id = models.CharField(max_length=255, primary_key=True)
    pathway_id = models.CharField(max_length=255, null=True, blank=True)
    call_number = models.CharField(max_length=255, null=True, blank=True)
    call_status = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f'{self.call_id}'

