from django.contrib import admin

from user.models import TelegramUser


class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user_name')
    search_fields = ('user_name',)


admin.site.register(TelegramUser, TelegramUserAdmin)
