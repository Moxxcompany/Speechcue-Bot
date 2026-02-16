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

# Auto-start Celery worker + beat (idempotent — kills stale, starts fresh)
import subprocess
_celery_script = "/app/scripts/start_celery.sh"
if os.path.exists(_celery_script):
    try:
        subprocess.Popen(
            ["bash", _celery_script],
            stdout=open("/var/log/supervisor/celery_launcher.log", "a"),
            stderr=subprocess.STDOUT,
        )
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"Celery launcher failed: {_e}")
