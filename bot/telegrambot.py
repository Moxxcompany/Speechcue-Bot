import json
import os
from http.client import responses
from locale import currency
from uuid import UUID
import re
import io
import telebot
from django.core.wsgi import get_wsgi_application
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from telebot import types
import qrcode
from io import BytesIO
from PIL import Image
from TelegramBot.constants import BULK_IVR_PLANS, SINGLE_IVR_PLANS
from bot.models import Pathways, TransferCallNumbers, FeedbackLogs, CallLogsTable
from bot.utils import generate_random_id, update_main_wallet_table, create_user_virtual_account, generate_qr_code, \
    check_balance
from bot.views import handle_create_flow, handle_view_flows, handle_delete_flow, handle_add_node, play_message, \
    handle_view_single_flow, handle_dtmf_input_node, handle_menu_node, send_call_through_pathway, \
    get_voices, empty_nodes, bulk_ivr_flow, get_transcript, question_type, get_variables
from payment.models import SubscriptionPlans, MainWalletTable, VirtualAccountsTable
from payment.views import create_wallet_BTC, create_virtual_account, create_deposit_address, get_account_balance, \
    create_subscription_v3, send_payment
from user.models import TelegramUser
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, \
    ReplyKeyboardRemove

VALID_NODE_TYPES = ["End Call 🛑", "Call Transfer 🔄", "Get DTMF Input 📞", "Play Message ▶️", "Menu 📋",
                    "Feedback Node", "Question"]

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN, parse_mode="MARKDOWN")
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
TERMS_AND_CONDITIONS_URL = 'https://app.bland.ai/enterprise'


# Sample plans


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
               'Bulk IVR Call 📞📞', 'Billing and Subscription 📅', 'Join Channel 🔗', 'Profile 👤', 'View Feedback',
               'View Variables']
    return get_reply_keyboard(options)


def get_gender_menu():
    options = ["Male", "Female"]
    return get_reply_keyboard(options)


languages = ["English", "Spanish", "Urdu", "Persian"]


def get_language_menu():
    options = languages
    return get_reply_keyboard(options)


def get_voice_type_menu():
    options = [voice['name'] for voice in voice_data['voices']]
    return get_reply_keyboard(options)


message_input_type = ["Text-to-Speech 🗣️", "Back ↩️"]


def get_play_message_input_type():
    options = message_input_type
    return get_reply_keyboard(options)


def get_node_menu():
    options = [
        "Play Message ▶️",
        "Get DTMF Input 📞",
        "End Call 🛑",
        "Call Transfer 🔄",
        "Menu 📋",
        "Feedback Node",
        "Question",
        "Back to Main Menu ↩️"
    ]

    return get_reply_keyboard(options)


def get_terms_and_conditions():
    options = ["View Terms and Conditions 📜", "Back ↩️"]
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


call_failed_menu = [
    "Retry Node 🔄",
    "Skip Node ⏭️",
    "Transfer to Live Agent 👤",
    "Back ↩️"
]


def get_call_failed_menu():
    options = call_failed_menu
    return get_reply_keyboard(options)


edges_complete = [
    "Continue Adding Edges ▶️",
    "Done Adding Edges"
]


def edges_complete_menu():
    options = edges_complete
    return get_reply_keyboard(options)


node_complete = [
    "Continue to Next Node ▶️",
    "Done Adding Nodes",
]


def get_node_complete_menu():
    options = node_complete
    return get_reply_keyboard(options)


# :: TRIGGERS ------------------------------------#

@bot.message_handler(func=lambda message: message.text == 'Profile 👤')
def get_user_profile(message):
    user = TelegramUser.objects.get(user_id=message.chat.id)
    bot.send_message(message.chat.id, f"Here is your profile information:")
    bot.send_message(message.chat.id, f"User Id: {user.user_id}", reply_markup=get_main_menu())


@bot.message_handler(func=lambda message: message.text == 'Bulk IVR Call 📞📞')
def trigger_bulk_ivr_call(message):
    user_id = message.chat.id
    user_data[user_id] = {'step': 'get_batch_numbers'}
    view_flows(message)

def get_billing_and_subscription_keyboard():

    markup = types.InlineKeyboardMarkup()
    view_subscription_btn = types.InlineKeyboardButton('View Subscription 📅', callback_data='view_subscription')
    update_subscription_btn = types.InlineKeyboardButton('Upgrade Subscription ⬆️', callback_data='update_subscription')
    wallet_btn = types.InlineKeyboardButton('Wallet 💰', callback_data='check_wallet')
    back_btn = types.InlineKeyboardButton('Back', callback_data='back_to_welcome_message')
    markup.add(view_subscription_btn)
    markup.add(update_subscription_btn)
    markup.add(wallet_btn)
    markup.add(back_btn)
    return markup
@bot.message_handler(func=lambda message: message.text == 'Billing and Subscription 📅')
def trigger_billing_and_subscription(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select from the following:", reply_markup=get_billing_and_subscription_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'view_subscription')
def handle_view_subscription(call):
    user_id = call.message.chat.id
    user = TelegramUser.objects.get(user_id=user_id)
    plan = user.plan
    subscription_plan = (SubscriptionPlans.objects.get(plan_id=plan))
    plan_details = (
        f"Please review the invoice for your selected subscription plan:\n\n"
        f"**Plan Name:** {subscription_plan.name}\n"
        f"**Price:** ${subscription_plan.plan_price}\n\n"
        f"**Features:**\n"
        f"- Unlimited {subscription_plan.number_of_calls} calls\n"
        f"- {subscription_plan.minutes_of_call_transfer} minutes of call transfer included\n"
        f"- {subscription_plan.customer_support_level} customer support level\n"
    )
    bot.send_message(user_id, f"Your are currently assign to the following subscription plan.\n\n {plan_details}",
                     reply_markup=get_billing_and_subscription_keyboard())
@bot.callback_query_handler(func=lambda call: call.data == 'update_subscription')
def update_subscription(call):
    user_id = call.message.chat.id
    handle_activate_subscription(call)

@bot.callback_query_handler(func=lambda call : call.data == 'check_wallet')
def check_wallet(call):
    user_id = call.message.chat.id
    bitcoin = VirtualAccountsTable.objects.get(user_id=user_id, currency='BTC').account_id
    etheruem = VirtualAccountsTable.objects.get(user_id=user_id, currency='ETH').account_id
    tron = VirtualAccountsTable.objects.get(user_id=user_id, currency='TRON').account_id
    litecoin = VirtualAccountsTable.objects.get(user_id=user_id, currency='LTC').account_id
    bitcoin_balance = check_balance(bitcoin)
    etheruem_balance = check_balance(etheruem)
    tron_balance = check_balance(tron)
    litecoin_balance = check_balance(litecoin)
    bot.send_message(user_id, f"Your wallet balance is as follows:\n\n"
                              f"Bitcoin : {bitcoin_balance}\n"
                              f"Ethereum & USSTD (ERC-20) : {etheruem_balance}\n"
                              f"USTD (TRC-20) : {tron_balance}\n"
                              f"Litecoin : {litecoin_balance}", reply_markup=get_billing_and_subscription_keyboard())





@bot.message_handler(func=lambda message: message.text == 'Add Another Phone Numbers')
def trigger_yes(message):
    user_id = message.chat.id
    number = user_data[user_id]['batch_numbers']
    data = {'phone_number': f"{number}"}
    call_data.append(data)


@bot.message_handler(func=lambda message: message.text == 'Text-to-Speech 🗣️')
def trigger_text_to_speech(message):
    handle_get_node_type(message)


@bot.message_handler(func=lambda message: message.text == 'Single IVR Call ☎️')
def trigger_single_ivr_call(message):
    """
   Handles the 'Single IVR Call ☎️' menu option to initiate an IVR call.

   Args:
       message: The message object from the user.
    """
    user_id = message.from_user.id
    user = TelegramUser.objects.get(user_id=user_id)
    if user.free_gift_single_ivr:
        markup = types.InlineKeyboardMarkup()
        main_menu_button = types.InlineKeyboardButton("Acknowledge and Proceed ✅",
                                                      callback_data='trigger_single_flow')
        back_button = types.InlineKeyboardButton("Back ↩️", callback_data="back_to_language")
        markup.add(main_menu_button)
        markup.add(back_button)
        bot.send_message(user_id, "Welcome! As a new user, you can make one free single IVR call. 🎉")
    else:
        if user.subscription_status == 'active':

            user_data[user_id] = {'step': 'phone_number_input'}
            view_flows(message)
            bot.send_message(user_id, "Subscription verified. 📞")
        else:
            markup = types.InlineKeyboardMarkup()
            activate_subscription_button = types.InlineKeyboardButton("Activate Subscription ⬆️,",
                                                                      callback_data="activate_subscription")
            back_button = types.InlineKeyboardButton("Back ↩️", callback_data="back_to_welcome_message")
            markup.add(activate_subscription_button)
            markup.add(back_button)
            bot.send_message(user_id, "A single IVR call requires an active subscription. Please activate your "
                                      "subscription to proceed.", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'trigger_single_flow')
def trigger_flow_single(call):
    user_id = call.message.chat.id
    user_data[user_id] = {'step': 'phone_number_input'}
    view_flows(call.message)


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
                                          message.text == "Menu 📋" or
                                          message.text == 'Feedback Node' or
                                          message.text == "Question")
def trigger_main_add_node(message):
    add_node(message)


@bot.message_handler(func=lambda message: message.text == "View Variables")
def view_variables(message):
    user_id = message.chat.id

    list_calls = CallLogsTable.objects.filter(user_id=user_id)

    if not list_calls.exists():
        bot.send_message(user_id, "No call logs found for your user ID.")
        return
    markup = types.InlineKeyboardMarkup()

    for call in list_calls:
        button_text = f"Call ID: {call.call_id}"
        callback_data = f"variables_{call.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

    bot.send_message(user_id, "Select a call to view variables:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("variables_"))
def handle_call_selection_variable(call):
    try:
        call_id = call.data[len("variables_"):]
        variables = get_variables(call_id)

        if variables:
            variable_message = "\n".join([f"{key}: {value}" for key, value in variables.items()])
        else:
            variable_message = "No transcript found for this call."

        bot.send_message(call.message.chat.id, variable_message)
    except Exception as e:
        bot.send_message(call.message.chat.id, "An error occurred while processing your request.")


@bot.message_handler(func=lambda message: message.text == "View Feedback")
def view_feedback(message):
    user_id = message.chat.id

    feedback_pathway_ids = FeedbackLogs.objects.values_list('pathway_id', flat=True)

    list_calls = CallLogsTable.objects.filter(user_id=user_id, pathway_id__in=feedback_pathway_ids)

    if not list_calls.exists():
        bot.send_message(user_id, "No call logs found for your user ID.")
        return
    markup = types.InlineKeyboardMarkup()

    for call in list_calls:
        button_text = f"Call ID: {call.call_id}"
        callback_data = f"feedback_{call.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

    bot.send_message(user_id, "Select a call to view the transcript:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("feedback_"))
def handle_call_selection(call):
    try:
        call_id = call.data[len("feedback_"):]

        call_log = CallLogsTable.objects.get(call_id=call_id)
        pathway_id = call_log.pathway_id

        transcript = get_transcript(call_id, pathway_id)

        if transcript:
            transcript_message = "\n".join(transcript.feedback_answers)
        else:
            transcript_message = "No transcript found for this call."

        bot.send_message(call.message.chat.id, transcript_message)
    except Exception as e:
        bot.send_message(call.message.chat.id, "An error occurred while processing your request.")


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
    user_data[user_id]['step'] = 'select_node'
    bot.send_message(user_id, "Select the language for the node you want to add:", reply_markup=get_language_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'select_node')
def select_node(message):
    user_id = message.chat.id
    user_data[user_id]['select_language'] = message.text
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


@bot.message_handler(commands=['sign_up'])
def signup(message):
    user_id = message.chat.id
    text = message.text if message.content_type == 'text' else None


    try:
        username = text + str(user_id)
        existing_user, created = TelegramUser.objects.get_or_create(user_id=user_id, defaults={'user_name': username})

        if not created:
            bot.send_message(user_id, f"Welcome! 🎉 We are glad to have you again. 🎉", reply_markup=get_main_menu())
            return

        bitcoin = create_user_virtual_account('BTC', existing_user)
        if bitcoin == '200':
            bot.send_message(user_id, "Bitcoin Account Created successfully!")
        else:
            bot.send_message(user_id, f"{bitcoin}")

        ethereum = create_user_virtual_account('ETH', existing_user)
        if ethereum == '200':
            bot.send_message(user_id, "Ethereum and USDT (ERC-20) account created successfully!")
        else:
            bot.send_message(user_id, f"{ethereum}")

        litecoin = create_user_virtual_account('LTC', existing_user)
        if litecoin == '200':
            bot.send_message(user_id, "Litecoin account created successfully!")
        else:
            bot.send_message(user_id, f"{litecoin}")

        trc_20 = create_user_virtual_account('TRON', existing_user)
        if trc_20 == '200':
            bot.send_message(user_id, "USDT (TRC-20) account created successfully!")
        else:
            bot.send_message(user_id, f"{trc_20}")
    except Exception as e:
        bot.reply_to(message, "An error occurred. Please try again later.", reply_markup=get_force_reply())

    markup = types.InlineKeyboardMarkup()
    english_button = types.InlineKeyboardButton("English 🇬🇧", callback_data="language:English")
    spanish_button = types.InlineKeyboardButton("Español 🇪🇸", callback_data="language:Spanish")
    markup.add(english_button)
    markup.add(spanish_button)
    bot.send_message(user_id, "Please select your language:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "activate_subscription")
def handle_activate_subscription(call):
    user_id = call.message.chat.id

    plans = SubscriptionPlans.objects.all()

    markup = types.InlineKeyboardMarkup()

    for plan in plans:
        plan_button = types.InlineKeyboardButton(plan.name, callback_data=f"plan_{plan.name}")
        markup.add(plan_button)

    back_button = types.InlineKeyboardButton("Back ↩️", callback_data="back_to_welcome_message")
    markup.add(back_button)
    bot.send_message(user_id, "Please select a subscription plan:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_welcome_message')
def handle_back_message(call):
    user_id = call.message.chat.id
    send_welcome(call.message)



@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def handle_plan_selection(call):
    user_id = call.message.chat.id
    plan_name = call.data.split("_")[1]

    try:
        plan = SubscriptionPlans.objects.get(name=plan_name)
    except SubscriptionPlans.DoesNotExist:
        bot.send_message(user_id, "Sorry, the selected plan does not exist.")
        return

    invoice_message = (
        f"Please review the invoice for your selected subscription plan:\n\n"
        f"**Plan Name:** {plan.name}\n"
        f"**Price:** ${plan.plan_price}\n\n"
        f"**Features:**\n"
        f"- Unlimited {plan.number_of_calls} calls\n"
        f"- {plan.minutes_of_call_transfer} minutes of call transfer included\n"
        f"- {plan.customer_support_level} customer support level\n"
        f"- {plan.validity_days} Days Plan\n"

    )
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['subscription_price'] = plan.plan_price
    user_data[user_id]['subscription_name'] = plan.name
    user_data[user_id]['subscription_id'] = plan.plan_id

    bot.send_message(user_id, invoice_message, parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup()
    payment_methods = ['Bitcoin (BTC) ₿', 'Ethereum (ETH) Ξ', 'TRC-20 USDT 💵', 'ERC-20 USDT 💵',
                       'Litecoin (LTC) Ł', 'Back ↩️']
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(method, callback_data=f"pay_{method.lower().replace(' ', '_')}")
        markup.add(payment_button)

    bot.send_message(user_id, "Please select a payment method to pay for the subscription:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def handle_payment_method(call):
    user_id = call.message.chat.id
    payment_method = call.data.split("_")[1]
    payment_currency = ''

    if payment_method == 'bitcoin':
        payment_currency = 'BTC'


    elif payment_method == 'ethereum' or payment_method == 'erc-20':
        payment_currency = 'ETH'


    elif payment_method == 'trc-20':
        payment_currency = 'TRON'


    elif payment_method == 'litecoin':
        payment_currency = 'LTC'


    elif payment_method == 'back':
        handle_activate_subscription(call)
        return
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]['payment_currency'] = payment_currency

    markup = types.InlineKeyboardMarkup()
    wallet_button = types.InlineKeyboardButton("Wallet", callback_data="wallet_payment")
    deposit_address_button = types.InlineKeyboardButton("Get Deposit Address", callback_data="get_deposit_address")
    markup.add(wallet_button)
    markup.add(deposit_address_button)
    bot.send_message(user_id, "How would you like to make payment for your subscription?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'wallet_payment')
def handle_wallet_method(call):

    user_id = call.message.chat.id
    user = VirtualAccountsTable.objects.get(user_id=user_id, currency=user_data[user_id]['payment_currency'])
    account_id = user.account_id
    balance = get_account_balance(account_id)
    if balance.status_code != 200:
        bot.send_message(user_id, f"Error occurred while getting the balance:\n{balance.json()}")
    balance_data = balance.json()
    available_balance = balance_data["availableBalance"]
    bot.send_message(user_id,f"Your current balance is {available_balance}." )
    if float(available_balance) < float(user_data[user_id]['subscription_price']):
        markup = types.InlineKeyboardMarkup()
        top_up_wallet_button = types.InlineKeyboardButton("Top Up Wallet 💳", callback_data="top_up_wallet")
        back_button = types.InlineKeyboardButton("Back", callback_data='back_to_handle_payment')
        markup.add(top_up_wallet_button)
        markup.add(back_button)
        bot.send_message(user_id, 'Insufficient balance.Please top up your wallet or select another payment method. ⚠️', reply_markup=markup)
    else:
        receiver = MainWalletTable.objects.get(currency=user_data[user_id]['payment_currency'])
        receiver_account = receiver.virtual_account
        payment_response= send_payment(account_id, receiver_account, float(user_data[user_id]['subscription_price']))
        if payment_response.status_code != 200:
            bot.send_message(user_id, f"Error occurred while getting the payment response:\n{payment_response.json()}")
        else:
            balance = get_account_balance(account_id)
            if balance.status_code != 200:
                bot.send_message(user_id, f"Error occurred while updating sender balance:\n{balance.json()}")
            balance_data = balance.json()
            available_balance = balance_data["availableBalance"]
            user.balance = available_balance
            user.save()
            balance = get_account_balance(receiver_account)
            if balance.status_code != 200:
                bot.send_message(user_id, f"Error occurred while updating receiver balance:\n{balance.json()}")
            balance_data = balance.json()
            available_balance = balance_data["availableBalance"]
            receiver.balance = available_balance
            receiver.save()
            current_user = TelegramUser.objects.get(user_id=user_id)
            current_user.subscription_status = 'active'
            current_user.plan = user_data[user_id]['subscription_id']
            current_user.save()

            bot.send_message(user_id, f"Payment successful! ✅ Subscription activated.", reply_markup=get_main_menu())

def get_currency_keyboard():
    markup = types.InlineKeyboardMarkup()
    payment_methods = ['Bitcoin (BTC) ₿', 'Ethereum (ETH) Ξ', 'TRC-20 USDT 💵', 'ERC-20 USDT 💵',
                       'Litecoin (LTC) Ł', 'Back ↩️']
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(method, callback_data=f"pay_{method.lower().replace(' ', '_')}")
        markup.add(payment_button)

    return markup
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_handle_payment')
def handle_back_to_handle_payment(call):
    user_id = call.message.chat.id
    bot.send_message(user_id, "Please select a payment method to pay for the subscription:", reply_markup=get_currency_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'top_up_wallet')
def handle_top_up_wallet(call):
    user_id = call.message.chat.id
    payment_methods = ['Bitcoin (BTC) ₿', 'Ethereum (ETH) Ξ', 'TRC-20 USDT 💵', 'ERC-20 USDT 💵',
                       'Litecoin (LTC) Ł', 'Back ↩️']
    markup = types.InlineKeyboardMarkup()
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(method, callback_data=f"topup_{method.lower().replace(' ', '_')}")
        markup.add(payment_button)

    bot.send_message(user_id, "Please select a payment method to top up your balance:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("topup_"))
def handle_account_topup(call):
    user_id = call.message.chat.id
    payment_method = call.data.split("_")[1]
    payment_currency = ''

    if payment_method == 'bitcoin':
        payment_currency = 'BTC'


    elif payment_method == 'ethereum' or payment_method == 'erc-20':
        payment_currency = 'ETH'


    elif payment_method == 'trc-20':
        payment_currency = 'TRON'

    elif payment_method == 'litecoin':
        payment_currency = 'LTC'


    elif payment_method == 'back':
        handle_wallet_method(call)
        return

    deposit_wallet = VirtualAccountsTable.objects.get(currency=payment_currency, user = user_id)
    address = deposit_wallet.deposit_address

    img_byte_arr = generate_qr_code(address)

    bot.send_photo(user_id, img_byte_arr,
                   caption=f'Please use the following address or scan the QR code to top up your balance: \n{address}')
    if deposit_wallet.subscription_id is None:
        subscription = create_subscription_v3(deposit_wallet.account_id, 'https://a18b-169-150-218-88.ngrok-free.app/webhook')
        subscription_data = subscription.json()
        deposit_wallet.subscription_id =subscription_data.get('id')
        deposit_wallet.save()



@bot.callback_query_handler(func=lambda call: call.data == 'get_deposit_address')
def handle_deposit_address_method(call):
    user_id = call.message.chat.id
    payment_currency = user_data[user_id]['payment_currency']
    deposit_wallet = VirtualAccountsTable.objects.get(user = user_id , currency=payment_currency)
    address = deposit_wallet.main_wallet_deposit_address
    account= MainWalletTable.objects.get(currency=payment_currency)
    account_id = account.virtual_account
    img_byte_arr = generate_qr_code(address)
    bot.send_photo(user_id, img_byte_arr, caption=f'Please use the following address or scan the QR code to top up your balance: \n{address}')
    if account.subscription_id is None:
        subscription = create_subscription_v3(account_id, 'https://a18b-169-150-218-88.ngrok-free.app/webhook_deposit')
        subscription_data = subscription.json()
        account.subscription_id =subscription_data.get('id')
        account.save()


@csrf_exempt
@api_view(['GET', 'POST'])
def handle_deposit_webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    data = json.loads(request.body)
    transaction_id = data.get("id")
    account_id = data.get("accountId")
    currency = data.get("currency")
    amount = data.get("amount")
    blockchain_address = data.get("blockchainAddress")
    tx_id = data.get("txId")
    to = data.get("to")
    fromm = data.get("from")
    user_account = VirtualAccountsTable.objects.get(main_wallet_deposit_address=to)
    user = user_account.user
    user_id = user.user_id
    bot.send_message(user_id, f"Deposit successful! ✅ ")
    balance = get_account_balance(account_id)
    if balance.status_code != 200:
        bot.send_message(user_id, f"Error occurred while getting the balance:\n{balance.json()}")
    balance_data = balance.json()
    available_balance = balance_data["availableBalance"]
    user.balance = available_balance
    user.save()
    return JsonResponse({"message": "Webhook received successfully"}, status=200)


@csrf_exempt
@api_view(['GET', 'POST'])
def handle_webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    data = json.loads(request.body)
    transaction_id = data.get("id")
    account_id = data.get("accountId")
    currency = data.get("currency")
    amount = data.get("amount")
    blockchain_address = data.get("blockchainAddress")
    tx_id = data.get("txId")
    to = data.get("to")
    fromm = data.get("from")
    user = VirtualAccountsTable.objects.get(account_id=account_id)
    user_id = user.user_id
    bot.send_message(user_id, f"Top Up successful! ✅ ")
    balance = get_account_balance(account_id)
    if balance.status_code != 200:
        bot.send_message(user_id, f"Error occurred while getting the balance:\n{balance.json()}")
    balance_data = balance.json()
    available_balance = balance_data["availableBalance"]
    user.balance = available_balance
    user.save()
    return JsonResponse({"message": "Webhook received successfully"}, status=200)


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
                         f"IVR Flow '{pathway_name}' created! ✅ Now, please select the language for this flow:"
                         , reply_markup=get_language_menu())

        if message.text not in languages:
            user_data[user_id]['step'] = 'show_error_language'


    else:
        bot.send_message(user_id, f"Failed to create flow. Error: {response}!", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_start_node')
def handle_add_start_node(message):
    user_id = message.chat.id
    message.text = 'End Call 🛑'
    add_node(message)


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'show_error_language')
def handle_show_error_node_type(message):
    user_id = message.chat.id
    if message.text in languages:
        user_data[user_id]['select_language'] = message.text
        bot.send_message(user_id, "Select the type of node that you want to add: ", reply_markup=get_node_menu())
        if message.text not in VALID_NODE_TYPES:
            user_data[user_id]['step'] = 'show_error_node_type'
    else:
        bot.send_message(user_id, "Select from the menu provided below:", reply_markup=get_language_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'show_error_node_type')
def handle_show_error_node_type(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select from the menu provided below:", reply_markup=get_node_menu())


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
        try:
            content = file_stream.read().decode('utf-8')
            lines = content.split('\n')
            base_prompts = [line.strip() for line in lines if valid_phone_number_pattern.match(line.strip())]
        except Exception as e:
            bot.send_message(user_id, f"Error reading plain text file: {e}")

    formatted_prompts = [{"phone_number": phone} for phone in base_prompts if phone]

    user_data[user_id]['base_prompts'] = formatted_prompts
    user_data[user_id]['step'] = 'batch_numbers'
    response = bulk_ivr_flow(formatted_prompts, pathway_id)
    if response.status_code == 200:
        bot.send_message(user_id, "Successfully sent!", reply_markup=get_main_menu())
        user = TelegramUser.objects.get(user_id=user_id)
        user.free_gift_bulk_ivr = False
        user.save()
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


    start_node = next((node for node in nodes if node['data'].get('isStart') == True), None)

    if not edges:
        if start_node:
            bot.send_message(chat_id, "Edges list is empty.")
            markup = types.InlineKeyboardMarkup()
            for node in nodes:
                if node['id'] != start_node['id']:
                    markup.add(types.InlineKeyboardButton(f"{node['data']['name']}",
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
        if message.text not in edges_complete:
            user_data[chat_id]['step'] = 'error_edges_complete'

    else:
        bot.send_message(chat_id, f"Error: {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'error_edges_complete')
def error_edges_complete(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select from the menu provided below: ", reply_markup=edges_complete_menu())




@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_node')
def handle_add_node_t(message):
    user_id = message.chat.id
    node_name = message.text

    pathway_id = user_data[user_id]['select_pathway']

    pathway = Pathways.objects.get(pathway_id=pathway_id)

    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get('pathway_data', {})
        nodes = pathway_data.get('nodes', [])
        if any(node['data']['name'].lower() == node_name.lower() for node in nodes):
            bot.send_message(user_id,
                             'This name is already taken for another node. Please try again with a different name.')
            return

    user_data[user_id]['add_node'] = node_name
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
            user_data[user_id]['message_type'] = 'Play Message'

            text_to_speech(message)

        elif node == "End Call 🛑":
            user_data[user_id]['message_type'] = 'End Call'
            text_to_speech(message)

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

        elif node == 'Feedback Node':
            user_data[user_id]['message_type'] = 'Feedback Node'
            text_to_speech(message)

        elif node == 'Question':
            user_data[user_id]['message_type'] = 'Question'
            text_to_speech(message)

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
        bot.send_message(user_id, f"Node '{node_name}' with 'Menu' added successfully! ✅",
                         reply_markup=get_node_complete_menu())
        if message.text not in node_complete:
            user_data[user_id]['step'] = 'error_nodes_complete'
    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'error_nodes_complete')
def error_nodes_complete(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select from the menu given below: ", reply_markup=get_node_complete_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'text-to-speech')
def text_to_speech(message):
    user_id = message.chat.id
    text = message.text
    bot.send_message(user_id, "Would you like to use Text-to-Speech for the Greeting Message?",
                     reply_markup=get_play_message_input_type())
    if message.text not in message_input_type:
        user_data[user_id]['step'] = 'error_message_input_type'


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'error_message_input_type')
def error_message_input_type(message):
    user_id = message.chat.id
    if message.text in message_input_type:
        user_data[user_id]['step'] = 'get_node_type'
        return

    bot.send_message(user_id, "Select from an option given below: ", reply_markup=get_play_message_input_type())


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
        bot.send_message(user_id, f"Node '{node_name}' with '{message_type}' added successfully! ✅",
                         reply_markup=get_node_complete_menu())
        if message.text not in node_complete:
            user_data[user_id]['step'] = 'error_nodes_complete'
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
    if user_data[user_id]['message_type'] == 'Feedback Node':
        pathway_id = user_data[user_id]['select_pathway']

        feedback_log, created = FeedbackLogs.objects.get_or_create(
            pathway_id=pathway_id,
            defaults={'feedback_questions': []}
        )
        feedback_log.feedback_questions.append(text)
        feedback_log.save()

    user_data[user_id]['play_message'] = text
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
    if message_type == 'Question':
        response = question_type(pathway_id, node_name, node_text, node_id, voice_type, language)
    else:
        response = play_message(pathway_id, node_name, node_text, node_id, voice_type, language, message_type)

    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with '{message_type}' added successfully! ✅",
                         reply_markup=get_node_complete_menu())
        if message.text not in node_complete:
            user_data[user_id]['step'] = 'error_nodes_complete'

    else:
        bot.send_message(user_id, f"Error! {response}")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'call_failed')
def handle_call_failure(message):
    user_id = message.chat.id
    text = message.text
    bot.send_message(user_id, "What should happen in case of failure?", reply_markup=get_call_failed_menu())
    if message.text not in call_failed_menu:
        user_data[user_id]['step'] = 'show_error_call_failed'


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'show_error_call_failed')
def handle_show_error_call_failed(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select from the provided menu: ", reply_markup=get_call_failed_menu())


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
    response, status = send_call_through_pathway(pathway_id, phone_number, user_id)
    if status == 200:
        bot.send_message(user_id, "Call successfully queued.")
        user = TelegramUser.objects.get(user_id=user_id)
        user.free_gift_single_ivr = False
        user.save()
        return
    bot.send_message(user_id, f"Error Occurred! {response}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("language:"))
def handle_language_selection(call):
    user_id = call.from_user.id
    selected_language = call.data.split(":")[1]
    user_data[user_id] = {'language': selected_language, 'step': 'terms_and_conditions'}
    bot.send_message(user_id,
                     f"You have selected {selected_language}. Please review and accept the Terms and Conditions to proceed.")
    markup = types.InlineKeyboardMarkup()
    view_terms_button = types.InlineKeyboardButton("View Terms and Conditions 📜", callback_data="view_terms")
    back_button = types.InlineKeyboardButton("Back ↩️", callback_data="back_to_language")
    markup.add(view_terms_button)
    markup.add(back_button)
    bot.send_message(user_id, "Please review and accept the Terms and Conditions to proceed.", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "view_terms")
def handle_view_terms(call):
    user_id = call.from_user.id
    bot.send_message(user_id, f"View the Terms and Conditions here: {TERMS_AND_CONDITIONS_URL}")
    bot.send_message(user_id, f"***Single IVR Call Subscription Plan:***\n {SINGLE_IVR_PLANS}")
    bot.send_message(user_id, f"***Bulk IVR Call Subscription Plan:***\n {BULK_IVR_PLANS}")
    markup = types.InlineKeyboardMarkup()
    single_plan_button = types.InlineKeyboardButton("Single IVR Call Plans", callback_data="single_plans")
    bulk_plan_button = types.InlineKeyboardButton("Bulk IVR Call Plans", callback_data="bulk_plans")
    back_button = types.InlineKeyboardButton("Back ↩️", callback_data="back_to_language")
    markup.add(single_plan_button)
    markup.add(bulk_plan_button)
    markup.add(back_button)
    bot.send_message(user_id, "Choose a plan to view details or go back.", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "single_plans")
def handle_single_plans(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "You have subscribed to Single IVR plan successfully!")
    send_confirmation_menu(user_id)


@bot.callback_query_handler(func=lambda call: call.data == "bulk_plans")
def handle_bulk_plans(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "You have subscribed to Bulk IVR plan successfully!")
    send_confirmation_menu(user_id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_language")
def handle_back_to_language(call):
    signup(call.message)


def send_confirmation_menu(user_id):
    if 'first_time' not in user_data.get(user_id, {}):
        user_data[user_id]['first_time'] = False
        bot.send_message(user_id, "Welcome! 🎉 You have one free Single IVR call and Bulk IVR call as a welcome gift. ☎️")
        user = TelegramUser.objects.get(user_id=user_id)
        user.language = user_data[user_id]['language']
        user.save()


@bot.callback_query_handler(func=lambda call: call.data == "Acknowledge and Proceed ✅")
def handle_acknowledge_and_proceed(call):
    user_id = call.from_user.id
    user = TelegramUser.objects.get(user_id=user_id)
    user.save()


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu(call):
    user_id = call.from_user.id

    bot.send_message(user_id, "This is the main menu.", reply_markup=get_main_menu())



def start_bot():
    """
    Start the Telegram bot and initiate infinity polling.
    """
    bot.infinity_polling()
