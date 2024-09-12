from django.contrib import admin
from .models import Pathways, CallLogsTable, CallDetails, TransferCallNumbers, FeedbackLogs, FeedbackDetails


class PathwaysAdmin(admin.ModelAdmin):
    list_display = ('pathway_id', 'pathway_name', 'pathway_user_id')  # Display key fields
    search_fields = ('pathway_name',)  # Add search by pathway name
    list_filter = ('pathway_user_id',)  # Optional: Filter by user


class CallLogsTableAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'call_number', 'pathway_id', 'user_id')  # Specify the fields to display in the list view
    search_fields = ('call_number', 'user_id')  # Add search functionality
    list_filter = ('user_id',)  # Filter by user


class CallDetailsAdmin(admin.ModelAdmin):
    list_display = ('call_id', 'call_details')  # Specify the fields to display
    search_fields = ('call_id',)  # Allow search by call_id


class TransferCallNumbersAdmin(admin.ModelAdmin):
    list_display = ('num_id', 'user_id', 'phone_number')  # Display these fields
    search_fields = ('phone_number', 'user_id')  # Search by phone number and user ID
    list_filter = ('user_id',)  # Filter by user


class FeedbackLogsAdmin(admin.ModelAdmin):
    list_display = ('pathway_id',)  # Only pathway_id since feedback_questions is an array
    search_fields = ('pathway_id',)  # Add search by pathway_id


class FeedbackDetailsAdmin(admin.ModelAdmin):
    list_display = ('call_id',)  # Only call_id since feedback_questions and answers are arrays
    search_fields = ('call_id',)  # Add search by call_id


# Registering the models in the Django admin
admin.site.register(Pathways, PathwaysAdmin)
admin.site.register(CallLogsTable, CallLogsTableAdmin)
admin.site.register(CallDetails, CallDetailsAdmin)
admin.site.register(TransferCallNumbers, TransferCallNumbersAdmin)
admin.site.register(FeedbackLogs, FeedbackLogsAdmin)
admin.site.register(FeedbackDetails, FeedbackDetailsAdmin)
