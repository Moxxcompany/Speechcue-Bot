from django.core.management.base import BaseCommand
from bot.telegrambot import start_bot


class Command(BaseCommand):
    help = 'Starts the Telegram bot'

    def handle(self, *args, **kwargs):
        start_bot()


