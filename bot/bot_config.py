import logging
import os, telebot
from django.core.wsgi import get_wsgi_application

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN, parse_mode="MARKDOWN")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TelegramBot.settings')
application = get_wsgi_application()
logging.basicConfig(level= logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

