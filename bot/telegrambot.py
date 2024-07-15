import os

import telebot
from django.core.wsgi import get_wsgi_application

from bot.models import Pathways
from bot.views import handle_create_flow, handle_view_flows, handle_delete_flow, handle_add_node, play_message
from user.models import TelegramUser

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN, parse_mode=None)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TelegramBot.settings')
application = get_wsgi_application()

available_commands = {
    '/name': 'Get a username!',
    '/help': 'Display all available commands!',
    '/create_flow': 'Create a new pathway',
    '/view_flows': 'Get all pathways',
    '/add_node': 'Add a node to the pathway'
}

user_data = {}


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """
    Sends a welcome message when the user starts a conversation.
    """
    welcome_message = "Hello there! Welcome to our bot. How can I help you today?\n\nUse /help to see available commands."
    bot.reply_to(message, welcome_message)


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


@bot.message_handler(commands=['create_flow'])
def create_flow(message):
    """
    Handle '/create_flow' command to initiate pathway creation.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    user_id = message.chat.id
    user_data[user_id] = {'step': 'ask_name'}
    bot.send_message(user_id, "Please enter the name of the pathway:")


@bot.message_handler(commands=['delete_flow'])
def delete_flow(message):
    """
    Handle '/delete_flow' command to initiate pathway deletion.

    Args:
        message (telebot.types.Message): The message object from Telegram.
    """
    user_id = message.chat.id
    user_data[user_id] = {'step': 'get_pathway'}
    bot.send_message(user_id, "Please enter the name of the pathway from the above list:")


@bot.message_handler(commands=['add_node'])
def add_node(message):
    """
    Handle '/add_node' command to initiate node addition.

    Args:
        message (telebot.types.Message): The message object from Telegram.
    """
    view_flows(message)
    user_id = message.chat.id
    user_data[user_id] = {'step': 'select_pathway'}
    bot.send_message(user_id, "Please enter the name of flow to add node:")


@bot.message_handler(commands=['view_flows'])
def view_flows(message):
    """
    Handle '/view_flows' command to retrieve all pathways.

    Args:
        message (telebot.types.Message): The message object from Telegram.

    Returns:
        None
    """
    pathways, status_code = handle_view_flows()
    if status_code != 200:
        bot.send_message(message.chat.id, f"Failed to fetch pathways. Error: {pathways.get('error')}")
        return

    current_users_pathways = Pathways.objects.filter(pathway_user_id=message.chat.id)
    user_pathway_ids = set(p.pathway_id for p in current_users_pathways)

    filtered_pathways = [pathway for pathway in pathways if pathway.get('id') in user_pathway_ids]

    if filtered_pathways:
        pathway_list = "\n".join(
            [f" - {pathway.get('name')} : {pathway.get('description')}" for pathway in filtered_pathways])
        bot.send_message(message.chat.id, f"List of pathways:\n\n{pathway_list}")
    else:
        bot.send_message(message.chat.id, "No pathways found.")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """
     Handle all messages except commands. Process user input for pathway creation or username registration.

     Args:
         message (telebot.types.Message): The message object from Telegram.
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
            response, status_code = handle_create_flow(pathway_name, pathway_description, user_id)

            if status_code == 200:
                bot.send_message(user_id,
                                 f"Pathway '{pathway_name}' with description '{pathway_description}' created "
                                 f"successfully.")
            else:
                bot.send_message(user_id, f"Failed to create pathway. Error: {response}!")
            del user_data[user_id]

        elif step == 'get_pathway':
            user_data[user_id]['get_pathway'] = text
            pathway = user_data[user_id]['get_pathway']
            current_users_pathways = Pathways.objects.filter(pathway_name=pathway)
            if not current_users_pathways.exists():
                bot.send_message(user_id, 'No pathway exists with this name')
                return
            pathway_id = current_users_pathways.first().pathway_id
            response, status_code = handle_delete_flow(pathway_id)

            if status_code == 200:
                bot.send_message(user_id, "Successfully deleted pathway.")
            else:
                bot.send_message(user_id, f"Error deleting pathway. Error: {response}!")
            del user_data[user_id]

        elif step == 'select_pathway':
            user_data[user_id]['select_pathway'] = text
            pathway = user_data[user_id]['select_pathway']
            current_users_pathways = Pathways.objects.filter(pathway_name=pathway)
            if not current_users_pathways.exists():
                bot.send_message(user_id, 'No pathway exists with this name')
                return
            pathway_id = current_users_pathways.first().pathway_id
            user_data[user_id]['select_pathway'] = pathway_id
            user_data[user_id]['step'] = 'add_node'
            bot.send_message(user_id, 'Please Enter name of your custom node')

        elif step == 'add_node':
            user_data[user_id]['add_node'] = text
            user_data[user_id]['step'] = 'add_node_id'
            bot.send_message(user_id, 'Please assign a number (0-9) for this node.')

        elif step == 'add_node_id':
            if text.isdigit() and 0 <= int(text) <= 9:
                user_data[user_id]['add_node_id'] = int(text)
                user_data[user_id]['step'] = 'get_node_type'
                bot.send_message(user_id, "Would you like to use \n:: a - Text-to-Speech\n:: b - Upload an audio file")
            else:
                bot.send_message(user_id, "Invalid input. Please enter a valid number between 0 and 9.")

        elif step == 'get_node_type':
            user_data[user_id]['get_node_type'] = text
            node_type = user_data[user_id]['get_node_type']
            pathway_id = user_data[user_id]['select_pathway']
            node_name = user_data[user_id]['add_node']
            node_text = "Hello World"
            node_id = user_data[user_id]['add_node_id']

            if node_type == 'a':
                response = play_message(pathway_id, node_name, node_text, node_id, "american", "male", "english")
                if response.status_code == 200:
                    bot.send_message(user_id, "Successfully Created!")
                else:
                    bot.send_message(user_id, f"Error! {response.text}")
                del user_data[user_id]

            elif node_type == 'b':
                # Handle the logic for uploading an audio file
                bot.send_message(user_id, "Please upload your audio file.")
                user_data[user_id]['step'] = 'upload_audio'

            else:
                bot.send_message(user_id, "Invalid input. Please choose 'a' or 'b'.")

        elif step == 'upload_audio':
            # Handle the audio file upload logic here
            bot.send_message(user_id, "Audio file received.")
            del user_data[user_id]

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
        bot.reply_to(message, "An error occurred. Please try again later.")


def start_bot():
    """
    Start the Telegram bot and initiate infinity polling.

    Returns:
        None
    """
    bot.infinity_polling()
