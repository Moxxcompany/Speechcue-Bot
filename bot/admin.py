from django.contrib import admin
from .models import Pathways, TransferCallNumbers


class PathwaysAdmin(admin.ModelAdmin):
    list_display = ('pathway_id', 'pathway_user_id')  # Specify the fields to display in the list view


class TransferCallNumbersAdmin(admin.ModelAdmin):
    list_display = ('num_id', 'user_id', 'phone_number')
    search_fields = ('phone_number',)


admin.site.register(Pathways, PathwaysAdmin)
admin.site.register(TransferCallNumbers, TransferCallNumbersAdmin)
