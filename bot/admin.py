from django.contrib import admin
from .models import (
    Pathways, CallLogsTable, CallDetails, TransferCallNumbers,
    FeedbackLogs, FeedbackDetails, CallDuration, BatchCallLogs
)


class PathwaysAdmin(admin.ModelAdmin):
    list_display = ('pathway_id', 'pathway_name', 'pathway_user_id', 'pathway_description', 'pathway_payload')
    search_fields = ('pathway_name', 'pathway_user_id')
    list_filter = ('pathway_user_id',)


class CallLogsTableAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'call_number', 'pathway_id', 'user_id', 'call_status')
    search_fields = ('call_number', 'user_id', 'call_status')
    list_filter = ('user_id', 'call_status')


class CallDetailsAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'call_details')
    search_fields = ('call_id',)


class TransferCallNumbersAdmin(admin.ModelAdmin):
    list_display = ('num_id', 'user_id', 'phone_number')
    search_fields = ('phone_number', 'user_id')
    list_filter = ('user_id',)


class FeedbackLogsAdmin(admin.ModelAdmin):
    list_display = ('pathway_id',)  # Display pathway_id since feedback_questions is an array
    search_fields = ('pathway_id',)


class FeedbackDetailsAdmin(admin.ModelAdmin):
    list_display = ('call_id',)  # Display call_id since feedback_questions and answers are arrays
    search_fields = ('call_id',)


class CallDurationAdmin(admin.ModelAdmin):
    list_display = (
        'call_id', 'pathway_id', 'user_id', 'duration_in_seconds',
        'start_time', 'end_time', 'queue_status', 'error_message',
        'additional_minutes', 'charged', 'notified'
    )
    search_fields = ('call_id', 'pathway_id', 'user_id', 'queue_status', 'error_message')
    list_filter = ('queue_status', 'start_time', 'end_time', 'charged', 'notified')


class BatchCallLogsAdmin(admin.ModelAdmin):
    list_display = (
        'call_id', 'batch_id', 'pathway_id', 'user_id', 'to_number',
        'from_number', 'call_status'
    )
    search_fields = ('call_id', 'batch_id', 'user_id', 'call_status')
    list_filter = ('user_id', 'call_status')


# Registering the models in the Django admin
admin.site.register(Pathways, PathwaysAdmin)
admin.site.register(CallLogsTable, CallLogsTableAdmin)
admin.site.register(CallDetails, CallDetailsAdmin)
admin.site.register(TransferCallNumbers, TransferCallNumbersAdmin)
admin.site.register(FeedbackLogs, FeedbackLogsAdmin)
admin.site.register(FeedbackDetails, FeedbackDetailsAdmin)
admin.site.register(CallDuration, CallDurationAdmin)
admin.site.register(BatchCallLogs, BatchCallLogsAdmin)
