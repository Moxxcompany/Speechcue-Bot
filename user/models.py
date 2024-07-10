from django.db import models


class TelegramUser(models.Model):
    user_id = models.BigIntegerField(primary_key=True)
    user_name = models.CharField(max_length=50)
