"""
Bridge module: Exposes Django ASGI application as `app` for uvicorn.
Supervisor runs: uvicorn server:app --host 0.0.0.0 --port 8001
"""
import sys
import os

# Add the Django project root to Python path
sys.path.insert(0, "/app")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TelegramBot.settings")

# Load env vars from /app/.env
from dotenv import load_dotenv
load_dotenv("/app/.env")

import django
django.setup()

# Import all telegrambot handlers so they register with the bot
import bot.telegrambot  # noqa: F401

from django.core.asgi import get_asgi_application
app = get_asgi_application()
