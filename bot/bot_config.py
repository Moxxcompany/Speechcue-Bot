import logging
import os, telebot
from django.core.wsgi import get_wsgi_application
from telebot.types import BotCommand, BotCommandScopeDefault

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN, parse_mode="MARKDOWN")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TelegramBot.settings')
application = get_wsgi_application()
logging.basicConfig(level= logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
global_language_variable = 'English'
user_data = {}
def clear_bot_commands(bot):
    bot.set_my_commands([])
    print("Old commands cleared!")

clear_bot_commands(bot)


def set_bot_commands(bot):
    bot.delete_my_commands(scope=BotCommandScopeDefault())  # Clear global commands explicitly
    print("Global commands cleared!")

    commands = [
        BotCommand("start", "Main Menu"),
        BotCommand("help", "Show Available Commands")
    ]
    bot.set_my_commands(commands, scope=BotCommandScopeDefault())  # Set global commands
    print("Global commands updated!")

set_bot_commands(bot)
def get_bot_commands(bot):
    commands = bot.get_my_commands()

    print("Currently set commands:")
    for command in commands:
        print(f"/{command.command}: {command.description}")

get_bot_commands(bot)