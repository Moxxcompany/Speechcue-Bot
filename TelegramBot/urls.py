"""
URL configuration for TelegramBot project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from bot import views as bot_views
from bot.telegrambot import crypto_transaction_webhook, payment_deposit_webhook
from bot import webhooks as webhook_views
from bot.telegram_webhook import telegram_webhook
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/telegram/webhook/", telegram_webhook, name="telegram_webhook"),
    path("create_flow/", bot_views.create_flow, name="create_flow"),
    path("view_flows/", bot_views.view_flows, name="view_flows"),
    path(
        "webhook/crypto_transaction",
        crypto_transaction_webhook,
        name="crypto_transaction_webhook",
    ),
    path(
        "call_details",
        webhook_views.call_details_webhook,
        name="call_details_webhook",
    ),
    path(
        "api/webhook/retell",
        webhook_views.retell_webhook,
        name="retell_webhook",
    ),
    path(
        "webhook/crypto_deposit", payment_deposit_webhook, name="crypto_deposit_webhook"
    ),
    path(
        "terms-and-conditions/",
        bot_views.terms_and_conditions,
        name="terms_and_conditions",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
