import uuid

from django.db import models

from user.models import TelegramUser


class SubscriptionPlans(models.Model):

    plan_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    plan_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    number_of_calls = models.IntegerField()
    minutes_of_call_transfer = models.IntegerField()
    customer_support_level = models.TextField(max_length=100)
    validity_days = models.CharField(max_length=100, blank=True, null=True)


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
    transfer_minutes_left = models.IntegerField(null=True, default=0)
    bulk_ivr_calls_left = models.IntegerField(null=True, default=0)
    date_of_subscription = models.DateField(auto_now_add=True, blank=True, null=True)
    date_of_expiry = models.DateField(null = True, blank=True)
