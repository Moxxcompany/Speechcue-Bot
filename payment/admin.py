from django.contrib import admin
from payment.models import SubscriptionPlans, MainWalletTable, VirtualAccountsTable, UserSubscription


@admin.register(SubscriptionPlans)
class SubscriptionPlansAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_price', 'number_of_calls', 'minutes_of_call_transfer', 'customer_support_level', 'validity_days')
    list_filter = ('plan_price', 'number_of_calls', 'customer_support_level', 'validity_days')
    search_fields = ('name', 'customer_support_level', 'validity_days')
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


@admin.register(MainWalletTable)
class MainWalletTableAdmin(admin.ModelAdmin):
    list_display = ('currency', 'xpub', 'address', 'virtual_account', 'mnemonic')
    search_fields = ('currency', 'address')
    list_filter = ('currency',)


@admin.register(VirtualAccountsTable)
class VirtualAccountsTableAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'account_detail', 'account_id')
    search_fields = ('user__username', 'account_detail', 'currency')
    list_filter = ('currency',)

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user_id_id', 'subscription_status', 'plan_id', 'transfer_minutes_left', 'bulk_ivr_calls_left')  # Display user_id_id instead of the object
    list_filter = ('subscription_status', 'plan_id')
    search_fields = ('user_id__id', 'subscription_status', 'plan_id__name')  # Search by user_id's actual id
    ordering = ('subscription_status', 'plan_id')

    fieldsets = (
        (None, {
            'fields': ('user_id', 'subscription_status')
        }),
        ('Plan Details', {
            'fields': ('plan_id', 'transfer_minutes_left', 'bulk_ivr_calls_left')
        }),
    )
