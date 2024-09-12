from django.contrib import admin
from payment.models import SubscriptionPlans

@admin.register(SubscriptionPlans)
class SubscriptionPlansAdmin(admin.ModelAdmin):
    list_display = (   'name', 'plan_price', 'number_of_calls', 'minutes_of_call_transfer', 'customer_support_level', 'validity_days')
    list_filter = ('plan_price', 'number_of_calls', 'customer_support_level' , 'validity_days')
    search_fields = ('name', 'customer_support_level','validity_days' )
    ordering = ('plan_price',)

    fieldsets = (
        (None, {
            'fields': ('name', 'plan_price', 'validity_days')
        }),
        ('Call Details', {
            'fields': ('number_of_calls', 'minutes_of_call_transfer')
        }),
        ('Support Details', {
            'fields': ('customer_support_level',)
        }),
    )
from django.contrib import admin
from .models import MainWalletTable, VirtualAccountsTable

@admin.register(MainWalletTable)
class MainWalletTableAdmin(admin.ModelAdmin):
    list_display = ('currency' , 'xpub', 'address', 'virtual_account', 'mnemonic')
    search_fields = ('currency', 'address')
    list_filter = ('currency',)

@admin.register(VirtualAccountsTable)
class VirtualAccountsTableAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'account_detail', 'account_id')
    search_fields = ('user__username', 'account_detail', 'currency')
    list_filter = ('currency',)

