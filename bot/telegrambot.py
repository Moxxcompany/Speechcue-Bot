import os
from uuid import UUID
import re
import io
import pandas as pd
import telebot
from django.core.wsgi import get_wsgi_application
from telebot import types

from bot.models import Pathways, TransferCallNumbers
from bot.utils import generate_random_id
from bot.views import handle_create_flow, handle_view_flows, handle_delete_flow, handle_add_node, play_message, \
    handle_view_single_flow, handle_dtmf_input_node, handle_menu_node, send_call_through_pathway, \
    get_voices, empty_nodes, bulk_ivr_flow
from user.models import TelegramUser
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

API_TOKEN = os.getenv('API_TOKEN')
print(API_TOKEN, "API_TOKENAPI_TOKENAPI_TOKENAPI_TOKENAPI_TOKEN")
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
voice_data = get_voices()
call_data = []


# :: MENUS ------------------------------------#


def get_reply_keyboard(options):
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for option in options:
        markup.add(KeyboardButton(option))
    return markup


def get_delete_confirmation_keyboard():
    options = [
        "Confirm Delete",
        "Back ↩️"
    ]
    return get_reply_keyboard(options)


def get_inline_keyboard(options):
    markup = InlineKeyboardMarkup()
    for option in options:
        markup.add(InlineKeyboardButton(option, callback_data=option))
    return markup


def get_force_reply():
    return ForceReply(selective=False)


def get_main_menu():
    options = ["Create IVR Flow ➕", "View Flows 📂", "Delete Flow ❌", "Help ℹ️", 'Single IVR Call ☎️',
               'Bulk IVR Call 📞📞']
    return get_reply_keyboard(options)


def get_gender_menu():
    options = ["Male", "Female"]
    return get_reply_keyboard(options)


def get_language_menu():
    options = ["English", "Spanish", "Urdu", "Persian"]
    return get_reply_keyboard(options)


def get_voice_type_menu():
    options = [voice['name'] for voice in voice_data['voices']]
    return get_reply_keyboard(options)


def get_play_message_input_type():
    options = ["Text-to-Speech 🗣️", "Back ↩️"]
    return get_reply_keyboard(options)


def get_node_menu():
    options = [
        "Play Message ▶️",
        "Get DTMF Input 📞",
        "End Call 🛑",
        "Call Transfer 🔄",
        "Menu 📋",
        "Back to Main Menu ↩️"
    ]

    return get_reply_keyboard(options)


def get_yes_no_keyboard():
    options = ["Add Another Phone Numbers", "Done Adding Phone Numbers"]
    return get_reply_keyboard(options)


def get_flow_node_menu():
    options = [
        "Add Node",
        "Delete Node",
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


def edges_complete_menu():
    options = [
        "Continue Adding Edges ▶️",
        "Done Adding Edges"
    ]
    return get_reply_keyboard(options)


def get_node_complete_menu():
    options = [
        "Continue to Next Node ▶️",
        "Done Adding Nodes",
    ]
    return get_reply_keyboard(options)


# :: TRIGGERS ------------------------------------#


@bot.message_handler(func=lambda message: message.text == 'Bulk IVR Call 📞📞')
def trigger_bulk_ivr_call(message):
    user_id = message.chat.id
    user_data[user_id] = {'step': 'get_batch_numbers'}
    view_flows(message)


@bot.message_handler(func=lambda message: message.text == 'Add Another Phone Numbers')
def trigger_yes(message):
    user_id = message.chat.id
    number = user_data[user_id]['batch_numbers']
    data = {'phone_number': f"{number}"}
    call_data.append(data)
    print(call_data)


# @bot.message_handler(func=lambda message: message.text == 'Done Adding Phone Numbers')
# def trigger_no(message):
#     bulk_ivr_flow()

@bot.message_handler(func=lambda message: message.text == 'Single IVR Call ☎️')
def trigger_single_ivr_call(message):
    """
   Handles the 'Single IVR Call ☎️' menu option to initiate an IVR call.

   Args:
       message: The message object from the user.
    """
    user_id = message.from_user.id
    user_data[user_id] = {'step': 'phone_number_input'}
    view_flows(message)


@bot.message_handler(func=lambda message: message.text == 'Back')
def trigger_back_flow(message):
    """
    Handles the 'Back' menu option to display previous flows.

    Args:
        message: The message object from the user.
    """
    display_flows(message)


@bot.message_handler(
    func=lambda message: message.text == 'Done Adding Nodes' or message.text == 'Continue Adding Edges ▶️')
def trigger_add_edges(message):
    """
    Handles the 'Done Adding Nodes' menu option to initiate edge addition.

    Args:
        message: The message object from the user.
    """
    handle_add_edges(message)


@bot.message_handler(func=lambda message: message.text == 'Confirm Delete')
def trigger_confirmation(message):
    """
    Handles the 'Confirm Delete' menu option to confirm deletion of a pathway.
    Args:
        message: The message object from the user.
    """
    handle_get_pathway(message)


@bot.message_handler(func=lambda message: message.text == 'Delete Node')
def trigger_delete_node(message):
    """
   Handles the 'Delete Node' menu option. Placeholder for future functionality.

   Args:
       message: The message object from the user.
   """
    pass


@bot.message_handler(func=lambda message: message.text == 'Retry Node 🔄')
def trigger_retry_node(message):
    """
    Handles the 'Retry Node 🔄' menu option to retry a node.

    Args:
        message: The message object from the user.
    """
    bot.send_message(message.chat.id, "Retry node")


@bot.message_handler(func=lambda message: message.text == 'Skip Node ⏭️')
def trigger_skip_node(message):
    """
    Handles the 'Skip Node ⏭️' menu option to skip a node.

    Args:
       message: The message object from the user.
    """
    bot.send_message(message.chat.id, "Skip node")


@bot.message_handler(func=lambda message: message.text == 'Transfer to Live Agent 👤')
def trigger_transfer_to_live_agent_node(message):
    transfer_to_agent(message)


@bot.message_handler(func=lambda message: message.text == 'Done Adding Edges')
def trigger_end_call_option(message):
    handle_call_failure(message)


@bot.message_handler(func=lambda message: message.text == 'Continue to Next Node ▶️')
def trigger_add_another_node(message):
    bot.send_message(message.chat.id, "Select the type of node you want to add next: ", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: message.text == 'Repeat Message 🔁')
def trigger_repeat_message(message):
    pass


@bot.message_handler(func=lambda message: message.text == 'Back to Main Menu ↩️' or message.text == 'Back ↩️')
def trigger_back(message):
    send_welcome(message)


@bot.message_handler(func=lambda message: message.text == "End Call 🛑" or
                                          message.text == "Call Transfer 🔄" or
                                          message.text == "Get DTMF Input 📞" or
                                          message.text == "Play Message ▶️" or
                                          message.text == "Menu 📋")
def trigger_main_add_node(message):
    add_node(message)


@bot.message_handler(func=lambda message: message.text == "Create IVR Flow ➕")
def trigger_create_flow(message):
    """
    Handle 'Create IVR Flow ➕' menu option.
    """
    create_flow(message)


@bot.callback_query_handler(func=lambda call: call.data == "create_ivr_flow")
def callback_create_ivr_flow(call):
    """
    Handle the 'Create IVR Flow ➕' button press.
    """
    create_flow(call.message)


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
def view_main_menu(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select the type of node you want to add:", reply_markup=get_node_menu())


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
    view_flows(message)

    bot.send_message(user_id, "Please select the flow you want to delete.")


@bot.message_handler(commands=['add_node'])
def add_node(message):
    """
    Handle '/add_node' command to initiate node addition.
    """
    user_id = message.chat.id

    if user_id not in user_data:
        user_data[user_id] = {}

    pathway_name = user_data[user_id].get('pathway_name')

    pathway = Pathways.objects.get(pathway_name=pathway_name)
    user_data[user_id]['step'] = 'add_node'
    user_data[user_id]['node'] = message.text
    user_data[user_id]['select_pathway'] = pathway.pathway_id
    bot.send_message(user_id, "Please enter the name of your custom node:", reply_markup=get_force_reply())


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
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    user_data[user_id]['pathway_name'] = pathway.pathway_name
    pathway, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        bot.send_message(user_id, f"Failed to fetch pathways. Error: {pathway.get('error')}")
        return
    pathway_info = f"Pathway Name: {pathway.get('name')}\nDescription: {pathway.get('description')}\n\nNodes:\n" + \
                   "\n".join(
                       [f"\n  Name: {node['data']['name']}\n"
                        for node in pathway['nodes']])

    bot.send_message(user_id, pathway_info, reply_markup=get_flow_node_menu())


@bot.message_handler(commands=['list_flows'])
def view_flows(message):
    """
    Handle '/list_flows' command to retrieve all pathways.
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
        markup.add(InlineKeyboardButton("Create IVR Flow ➕", callback_data="create_ivr_flow"))
        markup.add(InlineKeyboardButton("Back ↩️", callback_data="back"))
        bot.send_message(message.chat.id, "Please select an IVR Call Flow:", reply_markup=markup)
    else:
        markup.add(InlineKeyboardButton("Create IVR Flow ➕", callback_data="create_ivr_flow"))
        markup.add(InlineKeyboardButton("Back ↩️", callback_data="back"))
        bot.send_message(message.chat.id,
                         "You need to create an IVR flow before placing a call.\nPlease create a new IVR flow. ➕",
                         reply_markup=markup)


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
    response, status_code, pathway_id = handle_create_flow(pathway_name, pathway_description, user_id)

    if status_code == 200:
        res = empty_nodes(pathway_name, pathway_description, pathway_id)
        bot.send_message(user_id,
                         f"IVR Flow '{pathway_name}' created! ✅ Now, please select the type of node you want to add:"
                         , reply_markup=get_node_menu())

    else:
        bot.send_message(user_id, f"Failed to create flow. Error: {response}!", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_batch_numbers',
                     content_types=['text', 'document'])
def get_batch_call_base_prompt(message):
    user_id = message.chat.id
    pathway_id = user_data[user_id]['call_flow_bulk']

    valid_phone_number_pattern = re.compile(r'^[\d\+\-\(\)\s]+$')
    base_prompts = []

    if message.content_type == 'text':
        lines = message.text.split('\n')
        base_prompts = [line.strip() for line in lines if valid_phone_number_pattern.match(line.strip())]

    elif message.content_type == 'document':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_stream = io.BytesIO(downloaded_file)
        print("Processing plain text file")
        try:
            content = file_stream.read().decode('utf-8')
            print(f"File content: {content[:100]}")
            lines = content.split('\n')
            base_prompts = [line.strip() for line in lines if valid_phone_number_pattern.match(line.strip())]
        except Exception as e:
            print(f"Error reading plain text file: {e}")

    formatted_prompts = [{"phone_number": phone} for phone in base_prompts if phone]

    user_data[user_id]['base_prompts'] = formatted_prompts
    user_data[user_id]['step'] = 'batch_numbers'

    print(formatted_prompts)
    response = bulk_ivr_flow(formatted_prompts, pathway_id)
    if response.status_code == 200:
        bot.send_message(user_id, "Successfully sent!", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, f"Error: {response.text}", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'batch_numbers')
def get_batch_call_numbers(message):
    user_id = message.chat.id
    user_data[user_id]['batch_numbers'] = message.text
    bot.message_handler(user_id, "Do you want to add another number?")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_pathway')
def handle_get_pathway(message):
    user_id = message.chat.id
    text = message.text
    pathway_id = user_data[user_id]['select_pathway']
    response, status_code = handle_delete_flow(pathway_id)

    if status_code == 200:
        bot.send_message(user_id, "Flow deleted successfully! ✅", reply_markup=get_main_menu())
    else:
        bot.send_message(user_id, f"Error deleting pathway. Error: {response}!", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_pathway_'))
def handle_pathway_selection(call):
    user_id = call.message.chat.id
    pathway_id = call.data.split('_')[-1]
    pathway_id = UUID(pathway_id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]['select_pathway'] = pathway_id
    if 'step' in user_data.get(user_id, {}):
        step = user_data[user_id]['step']
    else:
        step = None
    if step is None:
        user_data[user_id]['step'] = 'add_node'
        bot.send_message(user_id, "Please enter the name of your custom node:", reply_markup=get_force_reply())
    elif step == 'get_pathway':
        bot.send_message(user_id, "Are you sure you want to delete this flow?",
                         reply_markup=get_delete_confirmation_keyboard())
    elif step == 'phone_number_input':
        user_data[user_id]['step'] = 'initiate_call'
        user_data[user_id]['call_flow'] = pathway_id
        bot.send_message(user_id, "Enter number with country code:")
    elif step == 'get_batch_numbers':
        user_data[user_id]['call_flow_bulk'] = pathway_id
        bot.send_message(user_id, "Please paste phone numbers (with country codes) or upload a file (TXT or CSV "
                                  "format) with up to 500 phone numbers.")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_edges')
def handle_add_edges(message):
    chat_id = message.chat.id
    pathway = Pathways.objects.get(pathway_name=user_data[chat_id]['pathway_name'])
    pathway_id = pathway.pathway_id
    response, status = handle_view_single_flow(pathway_id)
    if status != 200:
        bot.send_message(chat_id, f"Error: {response}", reply_markup=get_main_menu())
        return
    user_data[chat_id]['data'] = response
    edges = response.get("edges", [])
    nodes = response.get("nodes", [])
    user_data[chat_id]['node_info'] = nodes
    user_data[chat_id]['edge_info'] = edges
    start_node = next((node for node in nodes if node['data'].get('isStart')), None)

    if not edges:
        if start_node:
            bot.send_message(chat_id, "Edges list is empty.")
            markup = types.InlineKeyboardMarkup()
            for node in nodes:
                if node['id'] != start_node['id']:
                    markup.add(types.InlineKeyboardButton(f"{node['data']['name']} ({node['id']})",
                                                          callback_data=f"target_node_{node['id']}"))
            user_data[chat_id]['source_node_id'] = f"{start_node['id']}"
            bot.send_message(chat_id,
                             f"Start Node ID: {start_node['id']}\nStart Node Name: {start_node['data']['name']}\nPlease select another node to connect to the start node:",
                             reply_markup=markup)
        else:
            bot.send_message(chat_id, "No start node found.")
    else:
        markup = types.InlineKeyboardMarkup()
        for node in nodes:
            markup.add(types.InlineKeyboardButton(f"{node['data']['name']} ({node['id']})",
                                                  callback_data=f"source_node_{node['id']}"))
        bot.send_message(chat_id, "Select source node:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("source_node_"))
def handle_source_node(call):
    nodes = user_data[call.message.chat.id]['node_info']
    source_node_id = call.data.split("_")[2]
    user_data[call.message.chat.id]['source_node_id'] = source_node_id
    markup = types.InlineKeyboardMarkup()
    for node in nodes:
        if node['id'] != source_node_id:
            markup.add(types.InlineKeyboardButton(f"{node['data']['name']} ({node['id']})",
                                                  callback_data=f"target_node_{node['id']}"))
    bot.send_message(call.message.chat.id, "Select target node:", reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("target_node_"))
def handle_target_node(call):
    target_node_id = call.data.split("_")[2]
    chat_id = call.message.chat.id
    nodes = user_data[call.message.chat.id]['node_info']
    edges = user_data[call.message.chat.id]['edge_info']
    source_node_id = user_data[call.message.chat.id]['source_node_id']
    data = user_data[call.message.chat.id]['data']
    pathway_id = user_data[call.message.chat.id]['select_pathway']
    user_data[call.message.chat.id]['step'] = 'add_label'
    user_data[call.message.chat.id]['src'] = source_node_id
    user_data[call.message.chat.id]['target'] = target_node_id

    bot.send_message(call.message.chat.id,
                     "Enter Label: (Default: User Responds, For DTMF: User enters {your option}) ",
                     reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data[message.chat.id]['step'] == 'add_label')
def add_label(message):
    chat_id = message.chat.id
    label = message.text
    nodes = user_data[chat_id]['node_info']
    edges = user_data[chat_id]['edge_info']
    source_node_id = user_data[chat_id]['src']
    data = user_data[chat_id]['data']
    pathway_id = user_data[chat_id]['select_pathway']
    target_node_id = user_data[chat_id]['target']

    new_edge = {
        "id": f"reactflow__edge-{generate_random_id()}",
        "label": f"{label}",
        "source": f"{source_node_id}",
        "target": f"{target_node_id}"
    }
    edges.append(new_edge)
    updated_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "nodes": nodes,
        "edges": edges
    }
    response = handle_add_node(pathway_id, updated_data)
    if response.status_code == 200:
        bot.send_message(chat_id, f"Edge added from {source_node_id} node to {target_node_id} node!",
                         reply_markup=edges_complete_menu())
        pathway = Pathways.objects.get(pathway_id=pathway_id)
        pathway.pathway_name = data.get("name")
        pathway.pathway_description = data.get("description")
        pathway.pathway_payload = response.text
        pathway.save()
    else:
        bot.send_message(chat_id, f"Error: {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_node')
def handle_add_node_t(message):
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
        pathway_id = user_data[user_id]['select_pathway']
        existing_nodes = handle_view_single_flow(pathway_id)[0]['nodes']
        node_ids = [node['id'] for node in existing_nodes]
        if len(node_ids) == 10:
            bot.send_message(user_id, "All node ids between 0-9 are taken.")
            return
        if text in node_ids:
            bot.send_message(user_id, "This node ID is already assigned in the pathway. Please choose a different ID.")
            return

        user_data[user_id]['add_node_id'] = int(text)

        node = user_data[user_id]['node']
        if node == "Play Message ▶️":
            user_data[user_id]['step'] = 'get_node_type'
            user_data[user_id]['message_type'] = 'Play Message'
            bot.send_message(user_id, "Would you like to use Text-to-Speech for the Greeting Message?",
                             reply_markup=get_play_message_input_type())
        elif node == "End Call 🛑":
            user_data[user_id]['step'] = 'get_node_type'
            user_data[user_id]['message_type'] = 'End Call'
            bot.send_message(user_id, "Would you like to use Text-to-Speech for the Greeting Message?",
                             reply_markup=get_play_message_input_type())
        elif node == "Get DTMF Input 📞":
            user_data[user_id]['step'] = 'get_dtmf_input'
            user_data[user_id]['message_type'] = 'DTMF Input'
            bot.send_message(user_id, "Please enter the prompt message for DTMF input.", reply_markup=get_force_reply())
        elif node == 'Call Transfer 🔄':
            user_data[user_id]['step'] = 'get_dtmf_input'
            user_data[user_id]['message_type'] = 'Transfer Call'
            bot.send_message(user_id, "Please enter the phone number to transfer the call to",
                             reply_markup=get_force_reply())
        elif node == 'Menu 📋':
            user_data[user_id]['step'] = 'get_menu'
            bot.send_message(user_id, "Please enter the prompt message for the menu:", reply_markup=get_force_reply())


    else:
        bot.send_message(user_id, "Invalid input. Please enter a valid number between 0 and 9.",
                         reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_menu')
def get_menu(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['menu_message'] = text
    user_data[user_id]['step'] = 'get_action_list'
    bot.send_message(user_id, "Please assign numbers (0-9) and corresponding actions for each option.",
                     reply_markup=get_force_reply())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_action_list')
def get_action_list(message):
    user_id = message.chat.id
    text = message.text
    prompt = user_data[user_id]['menu_message']
    menu = text
    pathway_id = user_data[user_id]['select_pathway']
    node_name = user_data[user_id]['add_node']
    node_id = user_data[user_id]['add_node_id']
    response = handle_menu_node(pathway_id, node_id, prompt, node_name, menu)
    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with 'Menu' added successfully! ✅\nWhat should happen "
                                  f"after this node?", reply_markup=get_node_complete_menu())

    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'text-to-speech')
def text_to_speech(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['step'] = 'get_node_type'
    bot.send_message(user_id, "Would you like to use Text-to-Speech for the Greeting Message?",
                     reply_markup=get_play_message_input_type())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_dtmf_input')
def handle_get_dtmf_input(message):
    user_id = message.chat.id
    text = message.text
    pathway_id = user_data[user_id]['select_pathway']
    node_name = user_data[user_id]['add_node']
    prompt = text
    node_id = user_data[user_id]['add_node_id']
    message_type = user_data[user_id]['message_type']
    response = handle_dtmf_input_node(pathway_id, node_id, prompt, node_name, message_type)
    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with '{message_type}' added successfully! ✅\nWhat should happen "
                                  f"after this node?", reply_markup=get_node_complete_menu())

    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_node_type')
def handle_get_node_type(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['get_node_type'] = text
    node_type = user_data[user_id]['get_node_type']
    message_type = user_data[user_id]['message_type']
    if node_type == 'Text-to-Speech 🗣️':
        user_data[user_id]['step'] = 'play_message'
        bot.send_message(user_id, f"Please enter the prompt message for {message_type}: ",
                         reply_markup=get_force_reply())


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
    if text == 'Default John':
        text = 'f93094fc-72ac-4fcf-9cf0-83a7fff43e88'
    voice_type = next((voice for voice in voice_data['voices'] if voice['name'] == text), None)

    language = user_data[user_id]['select_language']
    message_type = user_data[user_id]['message_type']

    response = play_message(pathway_id, node_name, node_text, node_id, voice_type, language, message_type)
    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with '{message_type}' added successfully! ✅",
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
        bot.send_message(user_id, "You have finished adding nodes.", reply_markup=get_main_menu())
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


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'initiate_call')
def handle_single_ivr_call_flow(message):
    user_id = message.chat.id
    text = message.text
    user_data[user_id]['initiate_call'] = text
    pathway_id = user_data[user_id]['call_flow']
    phone_number = text
    response, status = send_call_through_pathway(pathway_id, phone_number)
    if status == 200:
        bot.send_message(user_id, "Call successfully queued.")
        return
    bot.send_message(user_id, f"Error Occurred! {response}")


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
