import os

import telebot
from django.core.wsgi import get_wsgi_application

from bot.views import handle_create_pathway, handle_get_all_pathways
from user.models import TelegramUser

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN, parse_mode=None)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TelegramBot.settings')
application = get_wsgi_application()

available_commands = {
    '/name': 'Get a username!',
    '/help': 'Display all available commands!',
    '/create_pathway': 'Create a new pathway',
    '/get_all_pathways': 'Get all pathways'
}

user_data = {}


@bot.message_handler(commands=['help'])
def show_commands(message):
    """
    Handle '/help' command to show available commands.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    formatted_commands = "\n".join(
        [f"{command} - {description}" for command, description in available_commands.items()])
    bot.send_message(message.chat.id, f"Available commands:\n{formatted_commands}")


@bot.message_handler(commands=['name'])
def send_welcome(message):
    """
    Handle '/name' command to initiate username collection.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    bot.reply_to(message, "Enter your name:")


@bot.message_handler(commands=['create_pathway'])
def create_pathway(message):
    """
    Handle '/create_pathway' command to initiate pathway creation.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    user_id = message.chat.id
    user_data[user_id] = {'step': 'ask_name'}
    bot.send_message(user_id, "Please enter the name of the pathway:")


@bot.message_handler(commands=['get_all_pathways'])
def get_all_pathways(message):
    """
    Handle '/get_all_pathways' command to retrieve all pathways.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    pathways, status_code = handle_get_all_pathways()
    if status_code != 200:
        bot.send_message(message.chat.id, f"Failed to fetch pathways. Error: {pathways.get('error')}")
        return

    if pathways:
        pathway_list = "\n".join(
            [f" - {pathway.get('name')} : {pathway.get('description')}" for pathway in pathways])
        bot.send_message(message.chat.id, f"List of pathways:\n\n{pathway_list}")
        return

    bot.send_message(message.chat.id, "No pathways found.")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """
    Handle all messages except commands. Process user input for pathway creation or username registration.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    user_id = message.chat.id
    text = message.text

    if user_id in user_data:
        step = user_data[user_id]['step']

        if step == 'ask_name':
            user_data[user_id]['pathway_name'] = text
            user_data[user_id]['step'] = 'ask_description'
            bot.send_message(user_id, "Please enter the description of the pathway:")
        elif step == 'ask_description':
            user_data[user_id]['pathway_description'] = text
            pathway_name = user_data[user_id]['pathway_name']
            pathway_description = user_data[user_id]['pathway_description']

            # Directly call the Django view function
            response = handle_create_pathway(pathway_name, pathway_description)

            # ToDo: handle_create_pathway returns tuple we are expecting Response object, need to fix this.
            if response.status_code == 200:
                bot.send_message(user_id,
                                 f"Pathway '{pathway_name}' with description '{pathway_description}' created successfully.")
            else:
                bot.send_message(user_id, f"Failed to create pathway. Error: {response.json().get('error')}")

            del user_data[user_id]  # Clear user data after use

        return

    try:
        username = text + str(user_id)
        existing_user, created = TelegramUser.objects.get_or_create(user_id=user_id, defaults={'user_name': username})
        if not created:
            if existing_user:
                bot.send_message(user_id, "Chat Id already Exists!")
                return
            TelegramUser.objects.create(user_id=user_id, user_name=username)

        bot.send_message(user_id, f"Hello, {text}! Welcome aboard. Your username is {username}")

    except TelegramUser.DoesNotExist:
        # Handle potential database errors gracefully (consider logging)
        bot.reply_to(message, "An error occurred. Please try again later.")


def start_bot():
    """
    Start the Telegram bot and initiate infinity polling.

    Returns:
        None
    """
    bot.infinity_polling()
