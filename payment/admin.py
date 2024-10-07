from django.contrib import admin

from payment.models import SubscriptionPlans, MainWalletTable, VirtualAccountsTable, UserSubscription


@admin.register(SubscriptionPlans)
class SubscriptionPlansAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_price', 'number_of_bulk_call_minutes', 'call_transfer', 'customer_support_level', 'validity_days')
    list_filter = ('plan_price', 'number_of_bulk_call_minutes', 'customer_support_level', 'validity_days')
    search_fields = ('name', 'customer_support_level', 'validity_days')
    ordering = ('plan_price',)

    fieldsets = (
        (None, {
            'fields': ('name', 'plan_price', 'validity_days')
        }),
        ('Call Details', {
            'fields': ('number_of_bulk_call_minutes', 'call_transfer')
        }),
        ('Support Details', {
            'fields': ('customer_support_level',)
        }),
    )


@admin.register(MainWalletTable)
class MainWalletTableAdmin(admin.ModelAdmin):
    list_display = ('currency', 'xpub', 'address', 'virtual_account', 'mnemonic', 'deposit_address', 'private_key' ,'subscription_id')
    search_fields = ('currency', 'address')
    list_filter = ('currency',)


@admin.register(VirtualAccountsTable)
class VirtualAccountsTableAdmin(admin.ModelAdmin):
    list_display = (
    'get_user_id', 'balance', 'currency', 'account_detail', 'account_id', 'subscription_id', 'deposit_address')
    search_fields = ('user__username', 'account_detail', 'currency')
    list_filter = ('currency',)

    def get_user_id(self, obj):
        return obj.user.user_id

    get_user_id.short_description = 'User ID'
@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    # Custom method to display the Telegram user_id
    def get_user_id(self, obj):
        return obj.user_id.user_id  # Access the user_id from the related TelegramUser

    get_user_id.short_description = 'User ID'  # This will change the column name in the admin interface

    list_display = ('get_user_id', 'subscription_status', 'plan_id', 'bulk_ivr_calls_left',
                    'date_of_subscription', 'date_of_expiry', 'call_transfer', 'auto_renewal')
    list_filter = ('subscription_status', 'plan_id')
    search_fields = ('user_id__user_id', 'subscription_status', 'plan_id__name')  # Search by the user_id directly
    ordering = ('subscription_status', 'plan_id')

    fieldsets = (
        (None, {
            'fields': ('user_id', 'subscription_status')
        }),
        ('Plan Details', {
            'fields': ('plan_id', 'call_transfer', 'bulk_ivr_calls_left', 'date_of_expiry')
        }),
    )