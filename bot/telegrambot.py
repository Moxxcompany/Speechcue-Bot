import os
from uuid import UUID

import telebot
from django.core.files.base import ContentFile
from django.core.wsgi import get_wsgi_application
from bot.models import Pathways, TransferCallNumbers
from bot.views import handle_create_flow, handle_view_flows, handle_delete_flow, handle_add_node, play_message, \
    handle_view_single_flow, handle_end_call, handle_dtmf_input_node
from user.models import TelegramUser
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

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


# :: MENUS ------------------------------------#


def get_reply_keyboard(options):
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for option in options:
        markup.add(KeyboardButton(option))
    return markup


def get_inline_keyboard(options):
    markup = InlineKeyboardMarkup()
    for option in options:
        markup.add(InlineKeyboardButton(option, callback_data=option))
    return markup


def get_force_reply():
    return ForceReply(selective=False)


def get_main_menu():
    options = ["Create IVR Flow ➕", "View Flows 📂", "Delete Flow ❌", "Help ℹ️"]
    return get_reply_keyboard(options)


def get_gender_menu():
    options = ["Male", "Female"]
    return get_reply_keyboard(options)


def get_language_menu():
    options = ["English", "Spanish", "Urdu", "Persian"]
    return get_reply_keyboard(options)


def get_voice_type_menu():
    options = ["Calm", "Enthusiastic", "Professional"]
    return get_reply_keyboard(options)


def get_play_message_input_type():
    options = ["Text-to-Speech 🗣️", "Back ↩️"]
    return get_reply_keyboard(options)


def get_node_menu():
    options = [
        "Play Message ▶️",
        "Get DTMF Input 📞",
        "Speech-to-Text 🎙️",
        "End Call 🛑",
        "Call Transfer 🔄",
        "Back to Main Menu ↩️"
    ]

    return get_reply_keyboard(options)


def get_flow_node_menu():
    options = [
        "Add Node",
        "Delete Node ",
        "Back"
    ]
    return get_reply_keyboard(options)


def get_call_failed_menu():
    options = [
        "Retry Node 🔄",
        "Skip Node ⏭️",
        "Transfer to Live Agent 👤",
        "Back ↩️"
    ]
    return get_reply_keyboard(options)


def get_node_complete_menu():
    print('#########')
    options = [
        "Continue to Next Node ▶️",
        "End Call🛑",
        "Repeat Message 🔁"
    ]
    return get_reply_keyboard(options)


# :: TRIGGERS ------------------------------------#

@bot.message_handler(func=lambda message: message.text == 'Retry Node 🔄')
def trigger_retry_node(message):
    bot.send_message(message.chat.id, "Retry node")


@bot.message_handler(func=lambda message: message.text == 'Skip Node ⏭️')
def trigger_skip_node(message):
    bot.send_message(message.chat.id, "Skip node")


@bot.message_handler(func=lambda message: message.text == 'Transfer to Live Agent 👤')
def trigger_transfer_to_live_agent_node(message):
    transfer_to_agent(message)


@bot.message_handler(func=lambda message: message.text == 'End Call🛑')
def trigger_end_call_option(message):
    handle_call_failure(message)


@bot.message_handler(func=lambda message: message.text == 'Continue to Next Node ▶️')
def trigger_add_another_node(message):
    bot.send_message(message.chat.id, "Select the type of node you want to add next: ", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: message.text == 'Repeat Message 🔁')
def trigger_repeat_message(message):
    pass


@bot.message_handler(func=lambda message: message.text == 'Back ↩️')
def trigger_back(message):
    send_welcome(message)


@bot.message_handler(func=lambda message: message.text == "Play Message ▶️")
def trigger_play_message(message):
    """
    Handle '"Play Message ▶️' menu option
    """
    add_node(message)


@bot.message_handler(func=lambda message: message.text == "Get DTMF Input 📞")
def trigger_dtmf_input(message):
    add_node(message)


@bot.message_handler(func=lambda message: message.text == "End Call 🛑")
def trigger_end_call(message):
    """
    Handle '"End Call 🛑' menu option
    """
    add_node(message)


@bot.message_handler(func=lambda message: message.text == "Create IVR Flow ➕")
def trigger_create_flow(message):
    """
    Handle 'Create IVR Flow ➕' menu option.
    """
    create_flow(message)


@bot.message_handler(func=lambda message: message.text == "View Flows 📂")
def trigger_view_flows(message):
    """
    Handle 'View Flows 📂' menu option.
    """
    display_flows(message)


@bot.message_handler(func=lambda message: message.text == "Delete Flow ❌")
def trigger_delete_flow(message):
    """
    Handle 'Delete Flow ❌' menu option.
    """
    delete_flow(message)


@bot.message_handler(func=lambda message: message.text == "Add Node")
def trigger_add_node_flow(message):
    """
    Handle 'Delete Flow ❌' menu option.
    """
    add_node(message)


# :: BOT MESSAGE HANDLERS FOR FUNCTIONS ------------------------------------#


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """
    Sends a welcome message when the user starts a conversation.
    """

    bot.send_message(message.chat.id, "Welcome to the Main Menu!", reply_markup=get_main_menu())


@bot.message_handler(commands=['help'])
def show_commands(message):
    """
    Handle '/help' command to show available commands.
    """
    formatted_commands = "\n".join(
        [f"{command} - {description}" for command, description in available_commands.items()])
    bot.send_message(message.chat.id, f"Available commands:\n{formatted_commands}", reply_markup=get_main_menu())


@bot.message_handler(commands=['name'])
def signup(message):
    """
    Handle '/name' command to initiate username collection.
    """
    bot.send_message(message.chat.id, "Enter your name:", reply_markup=get_force_reply())


@bot.message_handler(commands=['create_flow'])
def create_flow(message):
    """
    Handle '/create_flow' command to initiate pathway creation.
    """
    user_id = message.chat.id
    user_data[user_id] = {'step': 'ask_name'}
    bot.send_message(user_id, "Please enter the name of the pathway:", reply_markup=get_force_reply())


@bot.message_handler(commands=['delete_flow'])
def delete_flow(message):
    """
    Handle '/delete_flow' command to initiate pathway deletion.
    """
    user_id = message.chat.id
    user_data[user_id] = {'step': 'get_pathway'}
    bot.send_message(user_id, "Please enter the name of the pathway from the above list:",
                     reply_markup=get_force_reply())


@bot.message_handler(commands=['add_node'])
def add_node(message):
    """
    Handle '/add_node' command to initiate node addition.
    """

    user_id = message.chat.id
    #user_data[user_id]['node'] = message.text
    print(message.text)
    user_data[user_id] = {'step': 'select_pathway'}
    user_data[user_id] = {'node': message.text}

    view_flows(message)
    bot.send_message(user_id, "Please select the flow to add node:", reply_markup=get_force_reply())


@bot.message_handler(commands=['view_flows'])
def display_flows(message):
    """
    Handle '/view_flows' command to retrieve all pathways.
    """
    pathways, status_code = handle_view_flows()
    if status_code != 200:
        bot.send_message(message.chat.id, f"Failed to fetch pathways. Error: {pathways.get('error')}")
        return

    current_users_pathways = Pathways.objects.filter(pathway_user_id=message.chat.id)
    user_pathway_ids = set(p.pathway_id for p in current_users_pathways)

    filtered_pathways = [pathway for pathway in pathways if pathway.get('id') in user_pathway_ids]

    markup = InlineKeyboardMarkup()
    if filtered_pathways:
        pathway_buttons = [
            InlineKeyboardButton(pathway.get('name'), callback_data=f"view_pathway_{pathway.get('id')}")
            for pathway in filtered_pathways
        ]
        markup.add(*pathway_buttons)

    # Add the Back button at the end
    markup.add(InlineKeyboardButton("Back ↩️", callback_data="back"))

    bot.send_message(message.chat.id, "Here are your IVR flows:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'back')
def handle_back_button(call):
    """
    Handle the 'Back ↩️' button callback.
    """
    trigger_back(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('view_pathway_'))
def handle_pathway_details(call):
    """
    Handle the display of a pathway details from the inline keyboard.
    """
    user_id = call.message.chat.id
    pathway_id = call.data.split('_')[-1]
    pathway_id = UUID(pathway_id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['view_pathway'] = pathway_id

    pathway, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        bot.send_message(user_id, f"Failed to fetch pathways. Error: {pathway.get('error')}")
        return
    pathway_info = f"Pathway Name: {pathway.get('name')}\nDescription: {pathway.get('description')}\n\nNodes:\n" + \
                   "\n".join(
                       [f"\n  Name: {node['data']['name']}\n  Text: {node['data']['text']}\n" +
                        f"  Language: {node['data']['language']}\n" +
                        f"  Voice Type: {node['data']['voice_type']}\n  Voice Gender: {node['data']['voice_gender']}"
                        for node in pathway['nodes']])

    bot.send_message(user_id, pathway_info, reply_markup=get_flow_node_menu())


@bot.message_handler(commands=['list_flows'])
def view_flows(message):
    """
    Handle '/view_flows' command to retrieve all pathways.
    """
    pathways, status_code = handle_view_flows()
    if status_code != 200:
        bot.send_message(message.chat.id, f"Failed to fetch pathways. Error: {pathways.get('error')}")
        return

    current_users_pathways = Pathways.objects.filter(pathway_user_id=message.chat.id)
    user_pathway_ids = set(p.pathway_id for p in current_users_pathways)

    filtered_pathways = [pathway for pathway in pathways if pathway.get('id') in user_pathway_ids]

    markup = InlineKeyboardMarkup()
    if filtered_pathways:
        pathway_buttons = [
            InlineKeyboardButton(pathway.get('name'), callback_data=f"select_pathway_{pathway.get('id')}")
            for pathway in filtered_pathways
        ]
        markup.add(*pathway_buttons)

    # Add the Back button at the end
    markup.add(InlineKeyboardButton("Back ↩️", callback_data="back"))

    bot.send_message(message.chat.id, "list:", reply_markup=markup)


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'ask_name')
def handle_ask_name(message):
    user_id = message.chat.id
    text = message.text if message.content_type == 'text' else None

    if Pathways.objects.filter(pathway_name=text).exists():
        bot.send_message(user_id, "A flow with similar name already exists. Please enter the name again:")
        return
    user_data[user_id]['pathway_name'] = text
    user_data[user_id]['step'] = 'ask_description'
    bot.send_message(user_id, "Please enter the description of the pathway:", reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'ask_description')
def handle_ask_description(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['pathway_description'] = text
    pathway_name = user_data[user_id]['pathway_name']
    pathway_description = user_data[user_id]['pathway_description']
    response, status_code = handle_create_flow(pathway_name, pathway_description, user_id)

    if status_code == 200:
        bot.send_message(user_id,
                         f"IVR Flow '{pathway_name}' created! ✅ Now, please select the type of node you want to add:"
                         , reply_markup=get_node_menu())

    else:
        bot.send_message(user_id, f"Failed to create flow. Error: {response}!", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_pathway')
def handle_get_pathway(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['get_pathway'] = text
    pathway = user_data[user_id]['get_pathway']
    current_users_pathways = Pathways.objects.filter(pathway_name=pathway)
    if not current_users_pathways.exists():
        bot.send_message(user_id, 'No pathway exists with this name')
        return
    pathway_id = current_users_pathways.first().pathway_id
    response, status_code = handle_delete_flow(pathway_id)

    if status_code == 200:
        bot.send_message(user_id, "Successfully deleted pathway.", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, f"Error deleting pathway. Error: {response}!", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_pathway_'))
def handle_pathway_selection(call):
    """
    Handle the selection of a pathway from the inline keyboard.
    """
    user_id = call.message.chat.id
    pathway_id = call.data.split('_')[-1]
    pathway_id = UUID(pathway_id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['select_pathway'] = pathway_id
    user_data[user_id]['step'] = 'add_node'
    bot.send_message(user_id, "Please enter the name of your custom node:", reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_node')
def handle_add_node(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['add_node'] = text
    user_data[user_id]['step'] = 'add_node_id'
    bot.send_message(user_id, 'Please assign a number (0-9) for this node.', reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_node_id')
def handle_add_node_id(message):
    user_id = message.chat.id
    text = message.text
    if text.isdigit() and 0 <= int(text) <= 9:
        # Check if the node ID is already assigned in the pathway
        pathway_id = user_data[user_id]['select_pathway']
        existing_nodes = handle_view_single_flow(pathway_id)[0]['nodes']
        node_ids = [node['id'] for node in existing_nodes]
        print(node_ids)
        if len(node_ids) == 10:
            bot.send_message(user_id, "All node ids between 0-9 are taken.")
            return
        if int(text) in node_ids:
            bot.send_message(user_id, "This node ID is already assigned in the pathway. Please choose a different ID.")
            return

        user_data[user_id]['add_node_id'] = int(text)

        node = user_data[user_id]['node']
        print("in handle node id: ", node)
        if node == "Play Message ▶️":
            user_data[user_id]['step'] = 'get_node_type'
            bot.send_message(user_id, "Would you like to use Text-to-Speech for the Greeting Message?",
                             reply_markup=get_play_message_input_type())
        elif node == "End Call 🛑":
            # call for end call
            user_data[user_id]['step'] = 'end_call'
            bot.send_message(user_id, "Please enter goodbye prompt for user:", reply_markup=get_force_reply())
        elif node == "Get DTMF Input 📞":
            user_data[user_id]['step'] = 'get_dtmf_input'
            bot.send_message(user_id, "Please enter the prompt message for DTMF input.", reply_markup=get_force_reply())
    else:
        bot.send_message(user_id, "Invalid input. Please enter a valid number between 0 and 9.",
                         reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_dtmf_input')
def handle_get_dtmf_input(message):
    user_id = message.chat.id
    text = message.text
    pathway_id = user_data[user_id]['select_pathway']
    node_name = user_data[user_id]['add_node']
    prompt = text
    node_id = user_data[user_id]['add_node_id']

    response = handle_dtmf_input_node(pathway_id, node_id, prompt, node_name)
    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with 'DTMF Input' added successfully! ✅\nWhat should happen "
                                  f"after this node?", reply_markup=get_node_complete_menu())

    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'end_call')
def handle_end_call_bot(message):
    user_id = message.chat.id
    text = message.text
    pathway_id = user_data[user_id]['select_pathway']
    node_name = user_data[user_id]['add_node']
    prompt = text
    node_id = user_data[user_id]['add_node_id']

    response = handle_end_call(pathway_id, node_id, prompt, node_name)
    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with 'End Call' added successfully! ✅",
                         reply_markup=get_node_complete_menu())

    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_node_type')
def handle_get_node_type(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['get_node_type'] = text
    node_type = user_data[user_id]['get_node_type']

    if node_type == 'Text-to-Speech 🗣️':
        user_data[user_id]['step'] = 'play_message'
        bot.send_message(user_id, "Enter greeting message text: ", reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'play_message')
def handle_play_message(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['play_message'] = text
    user_data[user_id]['step'] = 'select_language'
    bot.send_message(user_id, "Please select a language", reply_markup=get_language_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'select_language')
def handle_select_language(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['select_language'] = text
    user_data[user_id]['step'] = 'select_gender'
    bot.send_message(user_id, "Please select a gender:", reply_markup=get_gender_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'select_gender')
def handle_select_gender(message):
    user_id = message.chat.id
    text = message.text

    user_data[user_id]['select_gender'] = text

    user_data[user_id]['step'] = 'select_voice_type'
    bot.send_message(user_id,
                     "Please select the type of voice.", reply_markup=get_voice_type_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'select_voice_type')
def handle_select_voice_type(message):
    user_id = message.chat.id
    text = message.text
    user_input = text
    pathway_id = user_data[user_id]['select_pathway']
    node_name = user_data[user_id]['add_node']
    node_text = user_data[user_id]['play_message']
    node_id = user_data[user_id]['add_node_id']
    voice_type = text
    voice_gender = user_data[user_id]['select_gender']
    language = user_data[user_id]['select_language']
    response = play_message(pathway_id, node_name, node_text, node_id, voice_type, voice_gender, language)
    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with 'Play Message' added successfully! ✅",
                         reply_markup=get_node_complete_menu())

    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'call_failed')
def handle_call_failure(message):
    user_id = message.chat.id
    text = message.text
    bot.send_message(user_id, "What should happen in case of failure?", reply_markup=get_call_failed_menu())


@bot.message_handler(commands=['transfer'])
def transfer_to_agent(message):
    user_id = message.chat.id
    phone_numbers = TransferCallNumbers.objects.filter(user_id=user_id).values_list('phone_number', flat=True)

    if phone_numbers:
        bot.send_message(user_id, "Do you want to use a previously entered phone number?",
                         reply_markup=get_reply_keyboard(['Yes', 'No']))
        user_data[user_id] = {'step': 'use_previous_number', 'phone_numbers': list(phone_numbers)}
    else:
        bot.send_message(user_id, "Please enter the phone number to transfer to.", reply_markup=get_force_reply())
        user_data[user_id] = {'step': 'enter_new_number'}


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'use_previous_number')
def handle_use_previous_number(message):
    user_id = message.chat.id
    text = message.text
    if text == 'Yes':
        phone_numbers = user_data[user_id]['phone_numbers']
        bot.send_message(user_id, "Please select the phone number to transfer to:",
                         reply_markup=get_inline_keyboard(phone_numbers))
        user_data[user_id]['step'] = 'select_phone_number'
    elif text == 'No':
        bot.send_message(user_id, "Please enter the phone number to transfer to.", reply_markup=get_force_reply())
        user_data[user_id]['step'] = 'enter_new_number'
    else:
        bot.send_message(user_id, "Please choose 'Yes' or 'No'.", reply_markup=get_reply_keyboard(['Yes', 'No']))


@bot.callback_query_handler(
    func=lambda call: user_data.get(call.message.chat.id, {}).get('step') == 'select_phone_number')
def handle_select_phone_number(call):
    user_id = call.message.chat.id
    phone_number = call.data
    user_data[user_id]['selected_phone_number'] = phone_number
    bot.send_message(user_id, "Settings saved.")
    bot.send_message(user_id, "Add another node or select 'Done' if you are finished.",
                     reply_markup=get_reply_keyboard(['Add Another Node', 'Done']))
    user_data[user_id]['step'] = 'add_or_done'


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'enter_new_number')
def handle_enter_new_number(message):
    user_id = message.chat.id
    phone_number = message.text
    # Save the new phone number for transfer and also save it to the TransferCallNumbers model
    TransferCallNumbers.objects.create(user_id=user_id, phone_number=phone_number)
    user_data[user_id]['selected_phone_number'] = phone_number
    bot.send_message(user_id, "Settings saved.")
    bot.send_message(user_id, "Add another node or select 'Done' if you are finished.",
                     reply_markup=get_reply_keyboard(['Add Another Node', 'Done']))
    user_data[user_id]['step'] = 'add_or_done'


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_or_done')
def handle_add_or_done(message):
    user_id = message.chat.id
    text = message.text
    if text == 'Add Another Node':
        user_data[user_id]['step'] = 'add_another_node'
        bot.send_message(user_id, "Please Select the type of node:", reply_markup=get_node_menu())

    elif text == 'Done':
        bot.send_message(user_id, "You have finished adding nodes.")
        del user_data[user_id]
    else:
        bot.send_message(user_id, "Please choose 'Add Another Node' or 'Done'.",
                         reply_markup=get_reply_keyboard(['Add Another Node', 'Done']))


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_another_node')
def handle_add_another_node(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['node'] = text
    user_data[user_id]['step'] = 'select_pathway'
    view_flows(message)
    bot.send_message(user_id, "Please enter the name of flow to add node:", reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: True, content_types=['text', 'audio'])
def echo_all(message):
    """
    Handle all messages except commands. Process user input for pathway creation or username registration.
    """
    user_id = message.chat.id
    text = message.text if message.content_type == 'text' else None
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
        bot.reply_to(message, "An error occurred. Please try again later.", reply_markup=get_force_reply())


def start_bot():
    """
    Start the Telegram bot and initiate infinity polling.
    """
    bot.infinity_polling()
