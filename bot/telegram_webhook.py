import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import telebot

from bot.bot_config import bot

logger = logging.getLogger(__name__)


@csrf_exempt
def telegram_webhook(request):
    """
    Receives Telegram updates via webhook and processes them.
    """
    if request.method == "POST":
        try:
            json_str = request.body.decode("utf-8")
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
            return JsonResponse({"status": "ok"})
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "method not allowed"}, status=405)
