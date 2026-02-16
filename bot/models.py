import uuid

from django.contrib.postgres.fields.array import ArrayField
from django.db import models

from user.models import TelegramUser


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


class AI_Assisted_Tasks(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_name = models.CharField(max_length=255, blank=True, null=True)
    task_description = models.TextField(blank=True, null=True)
    transcript = models.TextField(blank=True, null=True)
    user_id = models.BigIntegerField(blank=True, null=True)

    def __str__(self):
        return self.task


class CallerIds(models.Model):
    caller_id = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.caller_id


class UserPhoneNumber(models.Model):
    """Tracks phone numbers purchased by users via Retell."""
    user = models.ForeignKey(
        "user.TelegramUser", on_delete=models.CASCADE, related_name="phone_numbers"
    )
    phone_number = models.CharField(max_length=50, unique=True)
    country_code = models.CharField(max_length=5, default="US")
    area_code = models.IntegerField(null=True, blank=True)
    is_toll_free = models.BooleanField(default=False)
    nickname = models.CharField(max_length=100, blank=True, default="")
    monthly_cost = models.DecimalField(max_digits=6, decimal_places=2, default=2.00)
    purchased_at = models.DateTimeField(auto_now_add=True)
    next_renewal_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    # Voicemail settings
    voicemail_enabled = models.BooleanField(default=False)
    voicemail_message = models.TextField(blank=True, default="Please leave a message after the tone. We will get back to you shortly.")
    # Call forwarding settings
    forwarding_enabled = models.BooleanField(default=False)
    forwarding_number = models.CharField(max_length=50, blank=True, default="")
    # Business hours settings
    business_hours_enabled = models.BooleanField(default=False)
    business_hours_start = models.TimeField(null=True, blank=True)  # e.g. 09:00
    business_hours_end = models.TimeField(null=True, blank=True)    # e.g. 17:00
    business_hours_timezone = models.CharField(max_length=50, blank=True, default="US/Eastern")

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.phone_number} (user={self.user_id}, active={self.is_active})"


class PendingDTMFApproval(models.Model):
    """Tracks supervisor approval for DTMF input during single IVR calls.
    Retell custom function calls our endpoint, which creates this record
    and polls until the bot user approves/rejects via Telegram."""
    call_id = models.CharField(max_length=255)
    user_id = models.BigIntegerField()
    digits = models.CharField(max_length=50)
    node_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=20, default="pending",
        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("timeout", "Timeout")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["call_id", "status"]),
        ]

    def __str__(self):
        return f"DTMFApproval(call={self.call_id}, digits={self.digits}, status={self.status})"


class SMSInbox(models.Model):
    """Stores inbound SMS messages received on user's purchased Retell numbers."""
    user = models.ForeignKey(
        "user.TelegramUser", on_delete=models.CASCADE, related_name="sms_inbox"
    )
    phone_number = models.CharField(max_length=50)  # The Retell number that received SMS
    from_number = models.CharField(max_length=50)
    message = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_read"]),
        ]
        ordering = ["-received_at"]

    def __str__(self):
        return f"SMS from {self.from_number} to {self.phone_number}: {self.message[:50]}"


class PendingPhoneNumberPurchase(models.Model):
    """Tracks phone number purchase intent when paying via crypto.
    After crypto payment confirms and wallet is credited, this record
    triggers the auto-purchase flow."""
    user = models.ForeignKey(
        "user.TelegramUser", on_delete=models.CASCADE, related_name="pending_purchases"
    )
    country_code = models.CharField(max_length=5, default="US")
    area_code = models.IntegerField(null=True, blank=True)
    is_toll_free = models.BooleanField(default=False)
    monthly_cost = models.DecimalField(max_digits=6, decimal_places=2, default=2.00)
    created_at = models.DateTimeField(auto_now_add=True)
    is_fulfilled = models.BooleanField(default=False)
    is_failed = models.BooleanField(default=False)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_fulfilled"]),
        ]

    def __str__(self):
        return f"PendingPurchase(user={self.user_id}, {self.country_code}, fulfilled={self.is_fulfilled})"


class ActiveCall(models.Model):
    """Tracks live/ongoing calls for real-time billing."""
    call_id = models.CharField(max_length=255, primary_key=True)
    user_id = models.BigIntegerField()
    to_number = models.CharField(max_length=255)
    from_number = models.CharField(max_length=255, null=True, blank=True)
    region = models.CharField(max_length=100, default="US/Canada")
    rate_per_minute = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    call_type = models.CharField(max_length=20, default="single")  # single / bulk
    billing_source = models.CharField(max_length=20, default="plan")  # plan / wallet
    start_time = models.DateTimeField()
    last_billed_at = models.DateTimeField()
    total_billed = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    warning_sent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"ActiveCall {self.call_id} user={self.user_id} {self.region}"


class CampaignLogs(models.Model):
    user_id = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="campaign_user", null=True
    )
    campaign_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign_name = models.CharField(max_length=255, blank=True, null=True)
    total_calls = models.IntegerField(null=True, blank=True)
    avg_call_duration = models.FloatField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    batch_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.campaign_name


class ScheduledCalls(models.Model):
    user_id = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="schedule_call_user"
    )
    campaign_id = models.ForeignKey(
        CampaignLogs,
        on_delete=models.CASCADE,
        related_name="schedule_call_log",
        null=True,
        blank=True,
    )
    schedule_time = models.DateTimeField(null=True, blank=True)
    call_data = models.TextField(blank=True, null=True)
    caller_id = models.CharField(max_length=255, null=True, blank=True)
    task = models.TextField(blank=True, null=True)
    pathway_id = models.CharField(max_length=300, null=True, blank=True)
    call_status = models.BooleanField(default=False)
    canceled = models.BooleanField(default=False)


class ReminderTable(models.Model):
    user_id = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="reminder_user"
    )
    campaign_id = models.ForeignKey(
        CampaignLogs,
        on_delete=models.CASCADE,
        related_name="reminder_campaign_log",
        null=True,
        blank=True,
    )
    reminder_time = models.DateTimeField(null=True, blank=True)
    scheduled_call = models.ForeignKey(
        ScheduledCalls,
        on_delete=models.CASCADE,
        related_name="reminders",
        null=True,
        blank=True,
    )
    sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Reminder for Call {self.scheduled_call.id} at {self.reminder_time}"
