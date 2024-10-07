from django.contrib import admin

from user.models import TelegramUser


class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user_name', 'language', 'subscription_status', 'free_plan')
    search_fields = ('user_name','subscription_status', 'language')


admin.site.register(TelegramUser, TelegramUserAdmin)
