import uuid

from django.contrib.postgres.fields.array import ArrayField
from django.db import models


class Pathways(models.Model):
    pathway_id = models.TextField(primary_key=True)
    pathway_name = models.TextField()
    pathway_user_id = models.BigIntegerField()
    pathway_description = models.TextField(null=True)
    pathway_payload = models.TextField(null=True)
    dtmf = models.BooleanField(default=False)
    transcript = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.pathway_name


class CallLogsTable(models.Model):
    call_id = models.TextField(primary_key=True)
    call_number = models.TextField()
    pathway_id = models.TextField(null=True)
    user_id = models.BigIntegerField(null=True)
    call_status = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)


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


class BatchCallLogs(models.Model):
    call_id = models.TextField(primary_key=True)
    batch_id = models.TextField()
    pathway_id = models.TextField()
    user_id = models.BigIntegerField()
    to_number = models.CharField(max_length=255, null=True, blank=True)
    from_number = models.CharField(max_length=255, null=True, blank=True)
    call_status = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Call {self.call_id} Batch Call: {self.batch_id}"


class FrequentlyAskedQuestions(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField(max_length=255)
    answer = models.TextField()

    def __str__(self):
        return self.question


class Tasks(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.TextField(blank=True, null=True)
    transcript = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.task
