from django.db import models
from django_cryptography.fields import encrypt



class TelegramUser(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    user_name = models.CharField(max_length=50)
    language = models.CharField(max_length=50, null=True, default='English')
    plan = models.CharField(max_length=50, null=True, blank=True)
    subscription_status = models.CharField(max_length=50, null=True, default='inactive')
    free_plan = models.BooleanField(default=True)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.user_name
