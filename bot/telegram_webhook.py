import json
import logging
import threading

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import telebot

from bot.bot_config import bot

logger = logging.getLogger(__name__)


def _auto_answer_callback(update):
    """Automatically answer callback queries to prevent spinning buttons."""
    if update.callback_query:
        try:
            bot.answer_callback_query(update.callback_query.id)
        except Exception:
            pass  # Best-effort — don't block on answer failures


def _sync_user_info(update):
    """Capture chat_id + Telegram username on every interaction."""
    try:
        from bot.telegrambot import _sync_telegram_username
        from_user = None
        if update.message and update.message.from_user:
            from_user = update.message.from_user
        elif update.callback_query and update.callback_query.from_user:
            from_user = update.callback_query.from_user
        if from_user:
            _sync_telegram_username(from_user)
    except Exception:
        pass


@csrf_exempt
def telegram_webhook(request):
    """
    Receives Telegram updates via webhook and processes them.
    """
    if request.method == "POST":
        try:
            json_str = request.body.decode("utf-8")
            update = telebot.types.Update.de_json(json_str)
            # Auto-answer callback queries to prevent UI spinners
            _auto_answer_callback(update)
            # Sync user chat_id + username on every interaction
            _sync_user_info(update)
            bot.process_new_updates([update])
            return JsonResponse({"status": "ok"})
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "method not allowed"}, status=405)
