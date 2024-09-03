from django.db import models


class TelegramUser(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    user_name = models.CharField(max_length=50)
    language = models.CharField(max_length=50, null=True, default='English')
    plan = models.CharField(max_length=50, null=True)
    subscription_status = models.CharField(max_length=50, null=True, default='inactive')
    free_gift_single_ivr = models.BooleanField(default=True)
    free_gift_bulk_ivr = models.BooleanField(default=True)

class SubscriptionModel(models.Model):
    current_plan = models.CharField(max_length=50)
    subscription_status = models.CharField(max_length=50)
    metadata = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='subscriptions')

