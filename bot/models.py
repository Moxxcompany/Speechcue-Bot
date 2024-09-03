import uuid

from django.contrib.postgres.fields.array import ArrayField
from django.db import models


class Pathways(models.Model):
    pathway_id = models.TextField(primary_key=True)
    pathway_name = models.TextField()
    pathway_user_id = models.BigIntegerField()
    pathway_description = models.TextField(null=True)
    pathway_payload = models.TextField(null=True)


class CallLogsTable(models.Model):
    call_id = models.TextField(primary_key=True)
    call_number = models.TextField()
    pathway_id = models.TextField(null=True)
    user_id = models.BigIntegerField(null=True)


class CallDetails(models.Model):
    call_id = models.TextField(primary_key=True)
    call_details = models.TextField()


class TransferCallNumbers(models.Model):
    user_id = models.BigIntegerField()
    phone_number = models.TextField()
    num_id = models.CharField(max_length=40, primary_key=True, default=uuid.uuid4)

    def __str__(self):
        return self.phone_number


class FeedbackLogs(models.Model):
    pathway_id = models.TextField(primary_key=True)
    feedback_questions = ArrayField(models.TextField(), blank=True, default=list)


class FeedbackDetails(models.Model):
    call_id = models.TextField(primary_key=True)
    feedback_questions = ArrayField(models.TextField(), blank=True, default=list)
    feedback_answers = ArrayField(models.TextField(), blank=True, default=list)

