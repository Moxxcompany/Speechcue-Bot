import uuid
from django.contrib import admin
from bot.models import CallDuration
from payment.models import (
    SubscriptionPlans,
    MainWalletTable,
    VirtualAccountsTable,
    UserSubscription,
    OveragePricingTable,
    ManageFreePlanSingleIVRCall,
    UserTransactionLogs,
    TransactionType,
    PricingUnits,
    DTMF_Inbox,
)


@admin.register(DTMF_Inbox)
class DTMFInboxAdmin(admin.ModelAdmin):
    list_display = ("user_id_id", "call_id", "call_number", "dtmf_input", "timestamp")
    list_filter = ("timestamp", "user_id_id", "call_number")


@admin.register(SubscriptionPlans)
class SubscriptionPlansAdmin(admin.ModelAdmin):
    list_display = (
        "plan_id",
        "name",
        "plan_price",
        "single_ivr_minutes",
        "number_of_bulk_call_minutes",
        "call_transfer",
        "customer_support_level",
        "validity_days",
    )
    list_filter = (
        "plan_price",
        "number_of_bulk_call_minutes",
        "customer_support_level",
        "validity_days",
    )
    search_fields = ("name", "customer_support_level", "validity_days")
    ordering = ("plan_price",)
    fieldsets = (
        (None, {"fields": ("name", "plan_price", "validity_days")}),
        (
            "Call Details",
            {
                "fields": (
                    "number_of_bulk_call_minutes",
                    "single_ivr_minutes",
                    "call_transfer",
                )
            },
        ),
        ("Support Details", {"fields": ("customer_support_level",)}),
    )


@admin.register(MainWalletTable)
class MainWalletTableAdmin(admin.ModelAdmin):
    list_display = (
        "currency",
        "xpub",
        "address",
        "virtual_account",
        "mnemonic",
        "deposit_address",
        "private_key",
        "subscription_id",
        "fee",
        "gas_price",
        "gas_limit",
    )
    search_fields = ("currency", "address")
    list_filter = ("currency",)


@admin.register(VirtualAccountsTable)
class VirtualAccountsTableAdmin(admin.ModelAdmin):
    list_display = (
        "get_user_id",
        "balance",
        "currency",
        "account_detail",
        "account_id",
        "subscription_id",
        "deposit_address",
        "main_wallet_deposit_address",
    )
    search_fields = ("user__username", "account_detail", "currency")
    list_filter = ("currency",)

    def get_user_id(self, obj):
        return obj.user.user_id

    get_user_id.short_description = "User ID"


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    def get_user_id(self, obj):
        return obj.user_id.user_id

    get_user_id.short_description = "User ID"
    list_display = (
        "get_user_id",
        "subscription_status",
        "plan_id",
        "bulk_ivr_calls_left",
        "single_ivr_left",
        "date_of_subscription",
        "date_of_expiry",
        "call_transfer",
        "auto_renewal",
    )
    list_filter = ("subscription_status", "plan_id", "auto_renewal")
    search_fields = (
        "user_id__user_id",
        "subscription_status",
        "plan_id__name",
        "auto_renewal",
    )
    ordering = ("subscription_status", "plan_id")
    fieldsets = (
        (None, {"fields": ("user_id", "subscription_status", "auto_renewal")}),
        (
            "Plan Details",
            {
                "fields": (
                    "plan_id",
                    "call_transfer",
                    "bulk_ivr_calls_left",
                    "single_ivr_left",
                    "date_of_expiry",
                )
            },
        ),
    )


@admin.register(OveragePricingTable)
class OveragePricingTableAdmin(admin.ModelAdmin):
    list_display = ("overage_pricing", "pricing_unit")
    search_fields = ("overage_pricing", "pricing_unit")
    list_filter = ("overage_pricing", "pricing_unit")
    fieldsets = [
        ("Overage Pricing", {"fields": ["overage_pricing", "pricing_unit"]}),
    ]


@admin.register(ManageFreePlanSingleIVRCall)
class ManageFreePlanSingleIVRCallAdmin(admin.ModelAdmin):
    list_display = (
        "call_id",
        "get_user_id",
        "call_duration",
        "pathway_id",
        "call_number",
        "call_status",
    )
    search_fields = ("call_id", "user_id__user_id", "call_number", "call_status")
    list_filter = ("call_status",)

    def get_user_id(self, obj):
        return obj.user_id.user_id

    get_user_id.short_description = "User ID"


@admin.register(UserTransactionLogs)
class UserTransactionLogsAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "user_id",
        "reference",
        "transaction_type",
        "transaction_date",
    )
    search_fields = ("user_id", "reference", "transaction_type")
    list_filter = ("transaction_type", "transaction_date")
    ordering = ("-transaction_date",)
    fieldsets = (
        (
            None,
            {"fields": ("transaction_id", "user_id", "reference", "transaction_type")},
        ),
        ("Transaction Details", {"fields": ("transaction_date",)}),
    )
