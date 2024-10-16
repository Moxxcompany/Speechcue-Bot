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
    call_status = models.TextField(null=True)


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

class CallDuration(models.Model):
    call_id = models.CharField(max_length=255, primary_key=True)
    pathway_id = models.CharField(max_length=255)
    duration_in_seconds = models.FloatField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    queue_status = models.CharField(max_length=50, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    additional_minutes = models.FloatField(null=True, blank=True)
    user_id = models.BigIntegerField(null=True, blank=True)
    charged = models.BooleanField(default=False)
    notified = models.BooleanField(default=False)


    def __str__(self):
        return f"Call {self.call_id} Duration: {self.duration_in_seconds} seconds"

