from django.db import models



class TelegramUser(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    user_name = models.CharField(max_length=50)
    language = models.CharField(max_length=50, null=True, default='English')
    plan = models.CharField(max_length=50, null=True)
    subscription_status = models.CharField(max_length=50, null=True, default='inactive')
    free_plan = models.BooleanField(default=True)

