import json
import os
from locale import currency
from traceback import print_exc
from uuid import UUID
import re
import io
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

import bot.utils
from TelegramBot.constants import BITCOIN, ACCOUNT_CREATED_SUCCESSFULLY, \
    PROCESSING_ERROR, bitcoin, ethereum, BTC, ETH, trc20, erc20, TRON, litecoin, LTC, back, TOP_UP, \
    INSUFFICIENT_BALANCE, BACK, WALLET, DEPOSIT_ADDRESS, PAYMENT_METHOD_PROMPT, ETHEREUM, ERC, TRC, LITECOIN, \
    AVAILABLE_COMMANDS_PROMPT, SUBSCRIPTION_PLAN, NAME, BULK_IVR_LEFT, WALLET_INFORMATION, \
    USERNAME, PROFILE_INFORMATION_PROMPT, NO_SUBSCRIPTION_PLAN, JOIN_CHANNEL_PROMPT, INACTIVE, \
    BULK_IVR_SUBSCRIPTION_PROMPT, ACTIVE_SUBSCRIPTION_PLAN_PROMPT, SUBSCRIPTION_PLAN_NOT_FOUND, CHECKING_WALLETS, \
    PLAN_NAME, PRICE, FEATURES, CUSTOMER_SUPPORT_LEVEL, DAY_PLAN, UNLIMITED_SINGLE_IVR, BULK_IVR_CALLS, \
    SELECTION_PROMPT, WELCOME_PROMPT, PATHWAY_NOT_FOUND, NOT_FOUND, STATUS_CODE_200, ACTIVE, \
    INSUFFICIENT_DEPOSIT_AMOUNT, WEBHOOK_RECEIVED, invalid_data, INVALID_JSON, WEBHOOK_DEPOSIT, WEBHOOK, TOP_UP_PROMPT, \
    SUBSCRIPTION_PAYMENT_METHOD_PROMPT, USER_INFORMATION_NOT_FOUND, SUBSCRIPTION_ACTIVATED, MAIN_MENU_PROMPT, \
    PAYMENT_SUCCESSFUL, RECEIVERS_WALLET_NOT_FOUND, CURRENT_BALANCE, VIRTUAL_ACCOUNT_NOT_FOUND, CALL_TRANSFER_MINS, \
    INVOICE_REVIEW_PROMPT, PLAN_DOESNT_EXIST, DAYS, VALIDITY_PROMPT, PLAN_VALIDITY, VALIDITY, \
    SUBSCRIPTION_PLAN_SELECTION_PROMPT, NAME_INPUT_PROMPT, SETUP_PROMPT, EXISTING_USER_WELCOME, \
    LANGUAGE_SELECTION_PROMPT, USERNAME_PROMPT, NEW_USER_WELCOME, ACKNOWLEDGE_AND_PROCEED, NODE_TYPE_SELECTION_PROMPT, \
    TRANSCRIPT_NOT_FOUND, VIEW_TRANSCRIPT_PROMPT, CALL_LOGS_NOT_FOUND, VIEW_VARIABLES_PROMPT, EDGES_DELETED, \
    BALANCE_IN_USD, USD, CALL_TRANSFER_EXCLUDED, CALL_TRANSFER_INCLUDED, FULL_NODE_ACCESS, PARTIAL_NODE_ACCESS, \
    CALL_TRANSFER_NODE
from bot.models import Pathways, TransferCallNumbers, FeedbackLogs, CallLogsTable
from bot.utils import generate_random_id, create_user_virtual_account, generate_qr_code, \
    check_balance, set_user_subscription, convert_dollars_to_crypto, get_btc_price, get_eth_price, get_ltc_price, \
    get_trx_price, get_plan_price, check_validity, \
    check_subscription_status, username_formating, convert_crypto_to_usd, validate_transfer_number, validate_edges, \
    get_currency_symbol

from bot.views import handle_create_flow, handle_view_flows, handle_delete_flow, handle_add_node, play_message, \
    handle_view_single_flow, handle_dtmf_input_node, handle_menu_node, send_call_through_pathway, \
    get_voices, empty_nodes, bulk_ivr_flow, get_transcript, question_type, get_variables
from payment.models import SubscriptionPlans, MainWalletTable, VirtualAccountsTable, UserSubscription
from payment.views import  get_account_balance, \
    create_subscription_v3, send_payment

from user.models import TelegramUser
from bot.keyboard_menus import *
from bot.bot_config import *
from bot.callback_query_handlers import *

VALID_NODE_TYPES = ["End Call 🛑", "Call Transfer 🔄", "Get DTMF Input 📞", "Play Message ▶️", "Menu 📋",
                    "Feedback Node", "Question"]


available_commands = {
    '/create_flow': 'Create a new pathway',
    '/view_flows': 'Get all pathways',
    '/add_node': 'Add a node to the pathway'
}

user_data = {}

call_data = []


TERMS_AND_CONDITIONS_URL = os.getenv('TERMS_AND_CONDITIONS_URL')
CHANNEL_LINK = os.getenv('CHANNEL_LINK')

# :: TRIGGERS ------------------------------------#


@bot.message_handler(func=lambda message: message.text == 'Join Channel 🔗')
def handle_join_channel(message):

    user_id = message.chat.id

    # # Create an inline keyboard markup
    # keyboard = InlineKeyboardMarkup()
    #
    # # Add a "Join Channel" button with an embedded URL
    # join_channel_button = InlineKeyboardButton("Join Channel", url="https://www.google.com/")
    #
    # # Add a "Back" button with a callback to handle going back
    # back_button = InlineKeyboardButton("Back ↩️", callback_data=send_welcome(message))
    #
    # # Add buttons to the keyboard
    # keyboard.add(join_channel_button)
    # keyboard.add(back_button)

    # Send a message with the inline keyboard
    bot.send_message(user_id, f"{JOIN_CHANNEL_PROMPT}\n {CHANNEL_LINK}", reply_markup=get_main_menu())





@bot.message_handler(func=lambda message: message.text == 'Profile 👤')
def get_user_profile(message):
    user_id = message.chat.id
    user = TelegramUser.objects.get(user_id=message.chat.id)
    bot.send_message(user_id, f"{PROFILE_INFORMATION_PROMPT}")
    username_formated = user.user_name.replace('_', '\\_')
    bot.send_message(user_id, f"{USERNAME} : {username_formated}", parse_mode="Markdownv2" )
    if user.subscription_status == f'{INACTIVE}':
        bot.send_message(user_id, f"{NO_SUBSCRIPTION_PLAN}")
    else:
        user_plan = UserSubscription.objects.get(user_id=user.user_id)
        bot.send_message(user_id, f"{SUBSCRIPTION_PLAN}: \n"
                                  f"{NAME} :{user_plan.plan_id.name}\n"
                                  f"{BULK_IVR_LEFT} : {user_plan.bulk_ivr_calls_left}\n")
        bot.send_message(user_id, f"{WALLET_INFORMATION} \n")

        bitcoin = VirtualAccountsTable.objects.get(user_id=user_id, currency='BTC').account_id
        etheruem = VirtualAccountsTable.objects.get(user_id=user_id, currency='ETH').account_id
        tron = VirtualAccountsTable.objects.get(user_id=user_id, currency='TRON').account_id
        litecoin = VirtualAccountsTable.objects.get(user_id=user_id, currency='LTC').account_id
        sum_in_usd = 0
        bitcoin_balance = check_balance(bitcoin)
        balance_in_usd = convert_crypto_to_usd(float(bitcoin_balance), 'btc')
        sum_in_usd = sum_in_usd + balance_in_usd


        etheruem_balance = check_balance(etheruem)
        balance_in_usd = convert_crypto_to_usd(float(etheruem_balance), 'eth')
        sum_in_usd = sum_in_usd + balance_in_usd


        tron_balance = check_balance(tron)
        balance_in_usd = convert_crypto_to_usd(float(tron_balance), 'trx')
        sum_in_usd = sum_in_usd + balance_in_usd


        litecoin_balance = check_balance(litecoin)
        balance_in_usd = convert_crypto_to_usd(float(litecoin_balance), 'ltc')
        sum_in_usd = sum_in_usd + balance_in_usd


        bot.send_message(user_id, f"{BALANCE_IN_USD} : {sum_in_usd}", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == 'Help ℹ️')
def handle_help(message):
    user_id = message.chat.id
    bot.send_message(user_id, f"{AVAILABLE_COMMANDS_PROMPT}", reply_markup=get_available_commands())


@bot.message_handler(func=lambda message: message.text == 'Bulk IVR Call 📞📞')
@check_validity
def trigger_bulk_ivr_call(message):

    user_id = message.chat.id
    user = TelegramUser.objects.get(user_id=user_id)
    if user.subscription_status == 'active':
        user_data[user_id] = {'step': 'get_batch_numbers'}
        view_flows(message)
    else:
        bot.send_message(user_id, f"{BULK_IVR_SUBSCRIPTION_PROMPT}", reply_markup=get_subscription_activation_markup())

@bot.callback_query_handler(func=lambda call: call.data == 'help')
def handle_help_callback(call):
    handle_help(call.message)

@bot.message_handler(func=lambda message: message.text == 'Billing and Subscription 📅')
def trigger_billing_and_subscription(message):
    user_id = message.chat.id
    bot.send_message(user_id, f"{SELECTION_PROMPT}", reply_markup=get_billing_and_subscription_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'view_subscription')
@check_subscription_status
def handle_view_subscription(call):
    user_id = call.message.chat.id

    try:
        user = TelegramUser.objects.get(user_id=user_id)
        plan = user.plan

        subscription_plan = SubscriptionPlans.objects.get(plan_id=plan)

        plan_details = (
            f"**{PLAN_NAME}** {subscription_plan.name}\n"
            f"**{PRICE}** ${subscription_plan.plan_price}\n\n"
            f"**{FEATURES}**\n"
            f"- '{UNLIMITED_SINGLE_IVR}'\n"
            f"- {subscription_plan.number_of_bulk_call_minutes} {BULK_IVR_CALLS}\n"
            f"- {subscription_plan.customer_support_level} {CUSTOMER_SUPPORT_LEVEL}\n"
            f"- {subscription_plan.validity_days} {DAY_PLAN}\n"

        )
        if subscription_plan.call_transfer == True:
            plan_details+=(
                f"**Full Node Access** : Call Transfer included"
            )
        else:
            plan_details+=(
                f"**Partial Node Access** : Call Transfer not included"
            )

        bot.send_message(user_id, f"{ACTIVE_SUBSCRIPTION_PLAN_PROMPT}\n\n{plan_details}",
                         reply_markup=get_billing_and_subscription_keyboard())

    except TelegramUser.DoesNotExist:
        bot.send_message(user_id, f"{SUBSCRIPTION_PLAN_NOT_FOUND}",
                         reply_markup=get_billing_and_subscription_keyboard())

    except SubscriptionPlans.DoesNotExist:
        bot.send_message(user_id, f"{NO_SUBSCRIPTION_PLAN}",
                         reply_markup=get_billing_and_subscription_keyboard())


@bot.callback_query_handler(func=lambda call: call.data == 'update_subscription')
def update_subscription(call):
    user_id = call.message.chat.id
    handle_activate_subscription(call)


def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

@bot.callback_query_handler(func=lambda call: call.data == 'check_wallet')
def check_wallet(call):

    user_id = call.message.chat.id

    # Notify user that the process is being started
    bot.send_message(user_id, escape_markdown(f"{CHECKING_WALLETS}"), parse_mode='MarkdownV2')

    try:
        # Try to retrieve all virtual account information
        try:
            bitcoin_account = VirtualAccountsTable.objects.filter(user_id=user_id, currency='BTC').first()
            etheruem_account = VirtualAccountsTable.objects.filter(user_id=user_id, currency='ETH').first()
            tron_account = VirtualAccountsTable.objects.filter(user_id=user_id, currency='TRON').first()
            litecoin_account = VirtualAccountsTable.objects.filter(user_id=user_id, currency='LTC').first()

            if not bitcoin_account:
                raise ValueError("Bitcoin account not found.")
            if not etheruem_account:
                raise ValueError("Ethereum account not found.")
            if not tron_account:
                raise ValueError("Tron account not found.")
            if not litecoin_account:
                raise ValueError("Litecoin account not found.")

        except VirtualAccountsTable.DoesNotExist:
            bot.send_message(user_id, escape_markdown(f"{PROCESSING_ERROR}\n\nAccount details not found for one or more cryptocurrencies."), parse_mode='MarkdownV2')
            return

        sum_in_usd = 0

        # Fetch and convert balances for each cryptocurrency, ensuring errors are caught individually
        try:
            bitcoin_balance = check_balance(bitcoin_account.account_id)
            balance_in_usd = convert_crypto_to_usd(float(bitcoin_balance), 'btc')
            sum_in_usd += balance_in_usd
        except Exception as e:
            bot.send_message(user_id, escape_markdown(f"Error fetching or converting Bitcoin balance: {str(e)}"), parse_mode='MarkdownV2')
            return

        try:
            etheruem_balance = check_balance(etheruem_account.account_id)
            balance_in_usd = convert_crypto_to_usd(float(etheruem_balance), 'eth')
            sum_in_usd += balance_in_usd
        except Exception as e:
            bot.send_message(user_id, escape_markdown(f"Error fetching or converting Ethereum balance: {str(e)}"), parse_mode='MarkdownV2')
            return

        try:
            tron_balance = check_balance(tron_account.account_id)
            balance_in_usd = convert_crypto_to_usd(float(tron_balance), 'trx')
            sum_in_usd += balance_in_usd
        except Exception as e:
            bot.send_message(user_id, escape_markdown(f"Error fetching or converting Tron balance: {str(e)}"), parse_mode='MarkdownV2')
            return

        try:
            litecoin_balance = check_balance(litecoin_account.account_id)
            balance_in_usd = convert_crypto_to_usd(float(litecoin_balance), 'ltc')
            sum_in_usd += balance_in_usd
        except Exception as e:
            bot.send_message(user_id, escape_markdown(f"Error fetching or converting Litecoin balance: {str(e)}"), parse_mode='MarkdownV2')
            return

        # Create inline keyboard markup
        markup = InlineKeyboardMarkup()
        top_up_wallet_button = types.InlineKeyboardButton("Top Up Wallet 💳", callback_data="top_up_wallet")
        back_button = types.InlineKeyboardButton("Back", callback_data='back_to_billing')
        markup.add(top_up_wallet_button)
        markup.add(back_button)

        # Safely format and send the balance message using MarkdownV2 escaping
        bot.send_message(user_id, escape_markdown(f"{BALANCE_IN_USD}: {sum_in_usd:.2f} USD"), reply_markup=markup, parse_mode='MarkdownV2')

    except Exception as e:
        bot.send_message(user_id, escape_markdown(f"{PROCESSING_ERROR}\n\nUnexpected error: {str(e)}"), parse_mode='MarkdownV2')

    return
@bot.callback_query_handler(func=lambda call : call.data == 'back_to_billing')
def back_to_billing(call):
    user_id = call.message.chat.id
    bot.send_message(user_id, f"{SELECTION_PROMPT}", reply_markup=get_billing_and_subscription_keyboard())

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
@check_validity
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
        main_menu_button = types.InlineKeyboardButton(f"{ACKNOWLEDGE_AND_PROCEED}",
                                                      callback_data='trigger_single_flow')
        back_button = types.InlineKeyboardButton(f"{BACK} ↩️", callback_data="back_to_language")
        markup.add(main_menu_button)
        markup.add(back_button)
        bot.send_message(user_id, f"{NEW_USER_WELCOME}",reply_markup=markup )

    else:
        if user.subscription_status == 'active':
            bot.send_message(user_id, "Subscription verified. 📞")
            user_data[user_id] = {'step': 'phone_number_input'}
            view_flows(message)

        else:
            bot.send_message(user_id, "A single IVR call requires an active subscription. Please activate your "
                                      "subscription to proceed.", reply_markup=get_subscription_activation_markup())

@bot.callback_query_handler(func=lambda call: call.data == 'trigger_single_flow')
def trigger_flow_single(call):
    user_id = call.message.chat.id
    user_data[user_id] = {'step': 'phone_number_input'}
    view_flows(call.message)

@bot.message_handler(func=lambda message: message.text == 'Back')
def trigger_back_flow(message):
    user_id = message.chat.id
    bot.send_message(user_id, f"{WELCOME_PROMPT}", reply_markup=get_main_menu())


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
    user_id = message.chat.id
    pathway_id = user_data[user_id]['view_pathway']
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    user_data[user_id]['pathway_name'] = pathway.pathway_name
    pathway, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {pathway.get('error')}")
        return
    keyboard = InlineKeyboardMarkup()

    for node in pathway['nodes']:
        node_name = node['data']['name']
        button = InlineKeyboardButton(text=node_name, callback_data=f"delete_node_{node_name}")
        keyboard.add(button)
    bot.send_message(user_id, f"{SELECTION_PROMPT}", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_node_"))
def delete_node(call):
    user_id = call.message.chat.id
    node_name = call.data.replace("delete_node_", "")

    pathway_id = user_data[user_id]['view_pathway']
    try:
        pathway = Pathways.objects.get(pathway_id=pathway_id)
    except Pathways.DoesNotExist:
        bot.send_message(user_id, f"{PATHWAY_NOT_FOUND}")
        return

    pathway_payload = json.loads(pathway.pathway_payload)  # Parse payload as JSON

    nodes = pathway_payload['pathway_data']['nodes']
    node_id_to_delete = None

    for node in nodes:
        if node['data']['name'] == node_name:
            node_id_to_delete = node['id']
            break

    if not node_id_to_delete:
        bot.send_message(user_id, f"{node_name} {NOT_FOUND}")
        return

    new_nodes = [node for node in nodes if node['id'] != node_id_to_delete]
    edges = pathway_payload['pathway_data']['edges']
    new_edges = [edge for edge in edges if edge['source'] != node_id_to_delete and edge['target'] != node_id_to_delete]

    pathway_payload['pathway_data']['nodes'] = new_nodes
    pathway_payload['pathway_data']['edges'] = new_edges

    pathway.pathway_payload = json.dumps(pathway_payload)

    data = {
        "name": pathway_payload['pathway_data']['name'],
        "description": pathway_payload['pathway_data']['description'],
        "nodes": new_nodes,
        "edges": new_edges
    }

    updated = handle_add_node(pathway_id, data)

    if updated.status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR}\n"
                                  f"{updated.text}")
        return

    pathway.pathway_payload = updated.text
    pathway.save()


    bot.send_message(user_id, f"{node_name} {EDGES_DELETED}")

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
    chat_id = message.chat.id
    pathway_id = user_data[chat_id]['select_pathway']
    response, status_code = handle_view_single_flow(pathway_id)

    # Validate edges
    validation_result = validate_edges(response)
    missing_sources = validation_result['missing_sources']
    missing_targets = validation_result['missing_targets']
    valid = validation_result['valid']

    if not valid:
        if missing_sources:
            bot.send_message(chat_id,
                             f"The following nodes do not have any outgoing connections to other nodes: {', '.join(missing_sources)}")

        if missing_targets:
            bot.send_message(chat_id,
                             f"The following nodes do not connect to any other nodes: {', '.join(missing_targets)}")

        bot.send_message(chat_id, "At least, add one edge for the missing nodes!")
        handle_add_edges(message)
    else:
        handle_call_failure(message)


@bot.message_handler(func=lambda message: message.text == 'Continue to Next Node ▶️')
def trigger_add_another_node(message):
    bot.send_message(message.chat.id, f"{NODE_TYPE_SELECTION_PROMPT}", reply_markup=get_node_menu())

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
        bot.send_message(user_id, f"{CALL_LOGS_NOT_FOUND}")
        return
    markup = types.InlineKeyboardMarkup()

    for call in list_calls:
        button_text = f"Call ID: {call.call_id}"
        callback_data = f"variables_{call.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

    bot.send_message(user_id, f"{VIEW_VARIABLES_PROMPT}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("variables_"))
def handle_call_selection_variable(call):
    try:
        call_id = call.data[len("variables_"):]
        variables = get_variables(call_id)

        if variables:
            # Escape underscores only in the keys
            formatted_variables = []
            for key, value in variables.items():
                formatted_key = key.replace('_', '\\_')
                formatted_variables.append(f"{formatted_key}: {value}")

            variable_message = "\n".join(formatted_variables)
        else:
            variable_message = f"{TRANSCRIPT_NOT_FOUND}"

        bot.send_message(call.message.chat.id, variable_message, parse_mode="MarkdownV2")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"{PROCESSING_ERROR} {str(e)}")

@bot.message_handler(func=lambda message: message.text == "View Feedback")
def view_feedback(message):
    user_id = message.chat.id

    feedback_pathway_ids = FeedbackLogs.objects.values_list('pathway_id', flat=True)

    list_calls = CallLogsTable.objects.filter(user_id=user_id, pathway_id__in=feedback_pathway_ids)

    if not list_calls.exists():
        bot.send_message(user_id, f"{CALL_LOGS_NOT_FOUND}")
        return
    markup = types.InlineKeyboardMarkup()

    for call in list_calls:
        button_text = f"Call ID: {call.call_id}"
        callback_data = f"feedback_{call.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

    bot.send_message(user_id, f"{VIEW_TRANSCRIPT_PROMPT}", reply_markup=markup)

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
            transcript_message = f"{TRANSCRIPT_NOT_FOUND}"

        bot.send_message(call.message.chat.id, transcript_message)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"{PROCESSING_ERROR} {str(e)}")

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
    user_data[user_id]['first_node'] = False

    bot.send_message(user_id, f"{LANGUAGE_SELECTION_PROMPT}", reply_markup=get_language_markup('flowlanguage'))

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'select_node')
def select_node(message):
    user_id = message.chat.id
    user_data[user_id]['select_language'] = message.text
    bot.send_message(user_id, f"{NODE_TYPE_SELECTION_PROMPT}", reply_markup=get_node_menu())


# :: BOT MESSAGE HANDLERS FOR FUNCTIONS ------------------------------------#


def send_welcome(message):
    """
    Sends a welcome message when the user starts a conversation.
    """

    bot.send_message(message.chat.id, f"{WELCOME_PROMPT}", reply_markup=get_main_menu())


@bot.message_handler(commands=['help'])
def show_commands(message):
    """
    Handle '/help' command to show available commands.
    """
    formatted_commands = "\n".join(
        [f"{command} - {description}" for command, description in available_commands.items()])
    bot.send_message(message.chat.id, f"{AVAILABLE_COMMANDS_PROMPT}\n{formatted_commands}", reply_markup=get_main_menu())



def get_user_name(message):
    user_id = message.chat.id


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'profile_language')
def get_profile_language(message):
    user_id = message.chat.id
    text = message.text
    username = username_formating(text)
    username = f"{username}_{user_id}"
    username_formatting = username.replace('_', '\\_')
    bot.send_message(user_id, f"{USERNAME_PROMPT} {username_formatting}", parse_mode="MarkdownV2")
    user = TelegramUser.objects.get(user_id=user_id)
    user.user_name = username
    user.save()
    bot.send_message(user_id, f"{LANGUAGE_SELECTION_PROMPT}", reply_markup=get_language_markup('language'))
@bot.message_handler(commands=['cancel'])
def cancel_actions(message):
    user_id = message.chat.id
    bot.send_message(user_id, "You have cancelled the current action.\n"
                              "Redirecting you to the main menu!",
                     reply_markup = get_main_menu())


@bot.message_handler(commands=['sign_up', 'start'])
def signup(message):
    user_id = message.chat.id
    text = message.text if message.content_type == 'text' else None
    try:

        existing_user, created = TelegramUser.objects.get_or_create(user_id=user_id, defaults={'user_name': f'{user_id}'})

        if not created:
            bot.send_message(user_id, f"{EXISTING_USER_WELCOME}", reply_markup=get_main_menu())
            return
        bot.send_message(user_id, f"{SETUP_PROMPT}")
        bitcoin = create_user_virtual_account('BTC', existing_user)
        if bitcoin == f"{STATUS_CODE_200}":
            bot.send_message(user_id, f"{BITCOIN} {ACCOUNT_CREATED_SUCCESSFULLY}")
        else:
            bot.send_message(user_id, f"{PROCESSING_ERROR} {bitcoin.text()}")

        ethereum = create_user_virtual_account('ETH', existing_user)
        if ethereum == f"{STATUS_CODE_200}":
            bot.send_message(user_id, f"{ETHEREUM} & {ERC} {ACCOUNT_CREATED_SUCCESSFULLY}")
        else:
            bot.send_message(user_id, f"{PROCESSING_ERROR} {ethereum.text()}" )

        litecoin = create_user_virtual_account('LTC', existing_user)
        if litecoin == f"{STATUS_CODE_200}":
            bot.send_message(user_id, f"{LITECOIN} {ACCOUNT_CREATED_SUCCESSFULLY}")
        else:
            bot.send_message(user_id, f"{PROCESSING_ERROR} {litecoin.text()}")

        trc_20 = create_user_virtual_account('TRON', existing_user)
        if trc_20 == f"{STATUS_CODE_200}":
            bot.send_message(user_id, f"{TRC} {ACCOUNT_CREATED_SUCCESSFULLY}")
        else:
            bot.send_message(user_id, f"{PROCESSING_ERROR} {trc_20.text()}")

        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['step'] = 'profile_language'
        bot.send_message(user_id, f"{NAME_INPUT_PROMPT}")

        return

    except Exception as e:
        bot.reply_to(message, f"{PROCESSING_ERROR} {str(e)}", reply_markup=get_force_reply())
    get_profile_language(message)


@bot.callback_query_handler(func=lambda call: call.data == "activate_subscription")
def handle_activate_subscription(call):
    user_id = call.message.chat.id

    # Retrieve all plans from the database
    plans = SubscriptionPlans.objects.all()

    # Separate the free plan and other plans
    free_plan = None
    other_plans = []

    for plan in plans:
        if plan.plan_price == 0:  # Assuming the free plan has a price of 0
            free_plan = plan
        else:
            other_plans.append(plan)

    # Sort the other plans by validity_days (ensure they are integers)
    other_plans.sort(key=lambda p: (int(p.validity_days), p.plan_price))

    # Build the message text
    message_text = "Available subscription plans:\n\n"

    # Create InlineKeyboardMarkup object to store the buttons
    markup = types.InlineKeyboardMarkup()

    # Create a set to track unique plan names for buttons
    unique_plan_names = set()

    # Display the free plan at the top if it exists
    if free_plan:
        message_text += (f"🆔 {free_plan.name} Plan 📅\n"
                         f"💲 Free\n"
                         f"📞 {free_plan.number_of_bulk_call_minutes} Bulk IVR call minutes\n"
                         f"🔧 Customer Support Level: {free_plan.customer_support_level}\n"
                         f"📅 Validity: {free_plan.validity_days} Days\n\n")

        if free_plan.call_transfer:
            message_text += f"🔧 Full Node Access: Call Transfer Included\n\n"
        else:
            message_text += f"🔧 Partial Node Access: Call Transfer Excluded\n\n"

        # Create a button for the free plan
        plan_button = types.InlineKeyboardButton(free_plan.name, callback_data=f"plan_name_{free_plan.name}")
        markup.add(plan_button)

    # Iterate through the sorted other plans and build the message
    for plan in other_plans:
        # Add plan details to the message text
        message_text += (f"🆔 {plan.name} Plan 📅\n"
                         f"💲 ${plan.plan_price:.6f}\n"
                         f"📞 {plan.number_of_bulk_call_minutes} Bulk IVR call minutes\n"
                         f"🔧 Customer Support Level: {plan.customer_support_level}\n"
                         f"📅 Validity: {plan.validity_days} Days\n\n")

        if plan.call_transfer:
            message_text += f"🔧 Full Node Access: Call Transfer Included\n\n"
        else:
            message_text += f"🔧 Partial Node Access: Call Transfer Excluded\n\n"

        # Create a button for each unique plan name
        if plan.name not in unique_plan_names:
            unique_plan_names.add(plan.name)
            plan_button = types.InlineKeyboardButton(plan.name, callback_data=f"plan_name_{plan.name}")
            markup.add(plan_button)

    # Add a prompt at the end of the message
    message_text += "Please select a subscription plan below:"

    # Add a back button to go back to the welcome message
    back_button = types.InlineKeyboardButton(f"Back ↩️", callback_data="back_to_welcome_message")
    markup.add(back_button)

    # Send the message to the user with the markup (buttons)
    bot.send_message(user_id, message_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_name_"))
def view_plan_validity(call):
    user_id = call.message.chat.id
    plan_name = call.data.split("_")[2]
    plans = SubscriptionPlans.objects.filter(name=plan_name)
    message_text = f"{plan_name} {PLAN_VALIDITY}\n\n"
    for plan in plans:
        message_text += (f"🆔 {PLAN_NAME} {plan.name} Plan 📅\n"
                         f"💲 {PRICE} ${plan.plan_price:.6f}\n"
                         f"📞 {UNLIMITED_SINGLE_IVR} & {plan.number_of_bulk_call_minutes} {BULK_IVR_CALLS}\n"
                         f"🔧 {CUSTOMER_SUPPORT_LEVEL}: {plan.customer_support_level}\n"
                         f"📅 {VALIDITY} {plan.validity_days} {DAYS}\n\n")
        if plan.call_transfer:
            message_text += f"🔧 {FULL_NODE_ACCESS}: {CALL_TRANSFER_INCLUDED}\n\n"
        else:
            message_text += f"🔧 {PARTIAL_NODE_ACCESS}: {CALL_TRANSFER_EXCLUDED}\n\n"
    markup = types.InlineKeyboardMarkup()
    for plan in plans:
        plan_button = types.InlineKeyboardButton(f"{plan.validity_days} {DAYS}", callback_data=f"plan_{plan.plan_id}")
        markup.add(plan_button)

    bot.send_message(user_id, f"{message_text}\n{VALIDITY_PROMPT}\n\n", reply_markup=markup)



@bot.callback_query_handler(func=lambda call: call.data == 'back_to_welcome_message')
def handle_back_message(call):
    user_id = call.message.chat.id
    send_welcome(call.message)



@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def handle_plan_selection(call):
    user_id = call.message.chat.id
    plan_id = call.data.split("_")[1]

    try:
        plan = SubscriptionPlans.objects.get(plan_id=plan_id)
    except SubscriptionPlans.DoesNotExist:
        bot.send_message(user_id, f"{PLAN_DOESNT_EXIST}")
        return

    invoice_message = (
        f"🆔 {PLAN_NAME} {plan.name} Plan 📅\n"
                         f"💲 {PRICE} ${plan.plan_price:.6f}\n"
                         f"📞 {UNLIMITED_SINGLE_IVR} & {plan.number_of_bulk_call_minutes} {BULK_IVR_CALLS}\n"
                         f"🔧 {CUSTOMER_SUPPORT_LEVEL}: {plan.customer_support_level}\n"
                         f"📅 {VALIDITY} {plan.validity_days} {DAYS}\n\n")
    if plan.call_transfer:
        invoice_message += f"🔧 {FULL_NODE_ACCESS}: {CALL_TRANSFER_INCLUDED}\n\n"
    else:
        invoice_message += f"🔧 {PARTIAL_NODE_ACCESS}: CALL_TRANSFER_EXCLUDED\n\n"


    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['subscription_price'] = plan.plan_price
    user_data[user_id]['subscription_name'] = plan.name
    user_data[user_id]['subscription_id'] = plan.plan_id
    user = TelegramUser.objects.get(user_id=user_id)
    user.plan = plan.plan_id
    user.save()

    if plan.plan_price == 0:
        if user.free_plan:
            bot.send_message(user_id, invoice_message, parse_mode="Markdown")
            bot.send_message(user_id, f"You have successfully subscribed to {plan.name}. You have unlimited number "
                                      f"of SINGLE IVR calls, {plan.number_of_bulk_call_minutes} of BULK IVR calls, and "
                                      f"{plan.call_transfer} number of transfer call minutes valid "
                                      f"for {plan.validity_days} days.\n", reply_markup=get_main_menu())
            set_subscription = set_user_subscription(user, plan_id)
            if set_subscription != f"{STATUS_CODE_200}":
                bot.send_message(user_id, set_subscription)
            user.subscription_status = f"{ACTIVE}"
            user.free_plan = False
            user.save()

        else:
            bot.send_message(user_id, "You have already availed your free trial!", reply_markup=get_billing_and_subscription_keyboard())
        return
    markup = types.InlineKeyboardMarkup()
    payment_methods = ['Bitcoin (BTC) ₿', 'Ethereum (ETH) Ξ', 'TRC-20 USDT 💵', 'ERC-20 USDT 💵',
                       'Litecoin (LTC) Ł', 'Back ↩️']
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(method, callback_data=f"pay_{method.lower().replace(' ', '_')}")
        markup.add(payment_button)

    bot.send_message(user_id, f"{SUBSCRIPTION_PAYMENT_METHOD_PROMPT}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def handle_payment_method(call):
    user_id = call.message.chat.id
    payment_method = call.data.split("_")[1]
    payment_currency = ''

    if payment_method == f'{bitcoin}':
        payment_currency = f"{BTC}"


    elif payment_method == f'{ethereum}' or payment_method == f'{erc20}':
        payment_currency = f'{ETH}'


    elif payment_method == f'{trc20}':
        payment_currency = f'{TRON}'


    elif payment_method == f'{litecoin}':
        payment_currency = f'{LTC}'


    elif payment_method == f'{back}':
        handle_activate_subscription(call)
        return
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]['payment_currency'] = payment_currency
    print(payment_currency,  "currency ")

    markup = types.InlineKeyboardMarkup()
    wallet_button = types.InlineKeyboardButton(f"{WALLET}", callback_data="wallet_payment")
    deposit_address_button = types.InlineKeyboardButton(f"{DEPOSIT_ADDRESS}", callback_data="get_deposit_address")
    markup.add(wallet_button)
    markup.add(deposit_address_button)
    bot.send_message(user_id, f"{PAYMENT_METHOD_PROMPT}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'wallet_payment')
def handle_wallet_method(call):
    user_id = call.message.chat.id

    try:
        user = VirtualAccountsTable.objects.get(user_id=user_id, currency=user_data[user_id]['payment_currency'])

    except VirtualAccountsTable.DoesNotExist:
        bot.send_message(user_id, f"{VIRTUAL_ACCOUNT_NOT_FOUND}")
        return
    except Exception as e:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}")
        return

    try:
        account_id = user.account_id
        balance = get_account_balance(account_id)

        if balance.status_code != 200:
            bot.send_message(user_id, f"{PROCESSING_ERROR}\n{balance.json()}")
            return

        balance_data = balance.json()
        available_balance = int(balance_data["availableBalance"])
        symbol = get_currency_symbol(user_data[user_id]['payment_currency'])
        bot.send_message(user_id, f"{CURRENT_BALANCE} {available_balance:.6f} {symbol}.")
    except Exception as e:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}")
        return

    try:
        plan_price = float(user_data[user_id]['subscription_price'])
        plan_price = get_plan_price(user_data[user_id]['payment_currency'], plan_price)
        print(plan_price)

        if float(available_balance) < float(plan_price):
            markup = types.InlineKeyboardMarkup()
            top_up_wallet_button = types.InlineKeyboardButton(f"{TOP_UP}", callback_data="top_up_wallet")
            back_button = types.InlineKeyboardButton(f"{BACK}", callback_data='back_to_handle_payment')
            markup.add(top_up_wallet_button)
            markup.add(back_button)
            bot.send_message(user_id, f'{INSUFFICIENT_BALANCE}', reply_markup=markup)
            return

    except Exception as e:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}")
        return

    try:
        # Get the receiver's virtual account
        receiver = MainWalletTable.objects.get(currency=user_data[user_id]['payment_currency'])
        receiver_account = receiver.virtual_account

        # Send payment from user's account to receiver's account
        payment_response = send_payment(account_id, receiver_account, float(plan_price))

        if payment_response.status_code != 200:
            bot.send_message(user_id, f"{PROCESSING_ERROR} \n{payment_response.json()}")
            return

    except MainWalletTable.DoesNotExist:
        bot.send_message(user_id, f"{RECEIVERS_WALLET_NOT_FOUND}")
        return
    except Exception as e:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}")
        return

    try:
        # Update balances for both user and receiver
        balance = get_account_balance(account_id)
        if balance.status_code != 200:
            bot.send_message(user_id, f"{PROCESSING_ERROR}\n{balance.json()}")
            return

        balance_data = balance.json()
        available_balance = balance_data["availableBalance"]
        user.balance = available_balance
        user.save()

        balance = get_account_balance(receiver_account)
        if balance.status_code != 200:
            bot.send_message(user_id, f"{PROCESSING_ERROR}\n{balance.json()}")
            return

        balance_data = balance.json()
        available_balance = balance_data["availableBalance"]
        receiver.balance = available_balance
        receiver.save()

    except Exception as e:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}")
        return

    try:
        # Activate the subscription
        plan_id = user_data[user_id]['subscription_id']
        current_user = TelegramUser.objects.get(user_id=user_id)
        current_user.subscription_status = f'{ACTIVE}'
        current_user.plan = plan_id
        current_user.save()

        set_subscription = set_user_subscription(current_user, plan_id)
        if set_subscription != f"{STATUS_CODE_200}":
            bot.send_message(user_id, set_subscription)
            return

        send_confirmation_menu(user_id)
        bot.send_message(user_id, f"{PAYMENT_SUCCESSFUL} {SUBSCRIPTION_ACTIVATED} {MAIN_MENU_PROMPT}", reply_markup=get_main_menu())

    except TelegramUser.DoesNotExist:
        bot.send_message(user_id, f"{USER_INFORMATION_NOT_FOUND}")
    except Exception as e:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_handle_payment')
def handle_back_to_handle_payment(call):
    user_id = call.message.chat.id
    bot.send_message(user_id, f"{SUBSCRIPTION_PAYMENT_METHOD_PROMPT}", reply_markup=get_currency_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == 'top_up_wallet')
def handle_top_up_wallet(call):
    user_id = call.message.chat.id
    payment_methods = ['Bitcoin (BTC) ₿', 'Ethereum (ETH) Ξ', 'TRC-20 USDT 💵', 'ERC-20 USDT 💵',
                       'Litecoin (LTC) Ł', 'Back ↩️']
    markup = types.InlineKeyboardMarkup()
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(method, callback_data=f"topup_{method.lower().replace(' ', '_')}")
        markup.add(payment_button)

    bot.send_message(user_id, f"{TOP_UP_PROMPT}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("topup_"))
def handle_account_topup(call):
    currency_price = 0
    user_id = call.message.chat.id
    payment_method = call.data.split("_")[1]
    payment_currency = ''

    if payment_method == f'{bitcoin}':
        payment_currency = f'{BTC}'
        btc_price = get_btc_price()
        currency_price = btc_price


    elif payment_method == f'{ethereum}' or payment_method == f'{erc20}':
        payment_currency = f'{ETH}'
        eth_price = get_eth_price()
        currency_price = eth_price

    elif payment_method == f'{trc20}':
        payment_currency = f'{TRON}'
        tron_price = get_trx_price()
        currency_price = tron_price

    elif payment_method == f'{litecoin}':
        payment_currency = f'{LTC}'
        ltc_price = get_ltc_price()
        currency_price = ltc_price

    elif payment_method == f'{back}':
        handle_wallet_method(call)
        return
    # Convert to float
    deposit_wallet = VirtualAccountsTable.objects.get(currency=payment_currency, user=user_id)
    address = deposit_wallet.deposit_address

    img_byte_arr = generate_qr_code(address)

    if 'subscription_price' in user_data.get(user_id, {}):
        plan_price = float(user_data[user_id]['subscription_price'])
        plan_price = convert_dollars_to_crypto(plan_price, currency_price)

        bot.send_photo(user_id, img_byte_arr,
                   caption=f'Price for your subscription plan is {plan_price:.6f} in {payment_currency}.\n'
                           f'Please use the following address or scan the QR code to top up your balance! \n{address}')
    else:
        bot.send_photo(user_id, img_byte_arr,
                      caption=f'Please use the following address or scan the QR code to top up your balance! \n{address}')

    if deposit_wallet.subscription_id is None:
        subscription = create_subscription_v3(deposit_wallet.account_id, f'{os.getenv("webhook_url")}/{WEBHOOK}')
        subscription_data = subscription.json()
        deposit_wallet.subscription_id = subscription_data.get('id')
        deposit_wallet.save()

@bot.callback_query_handler(func=lambda call: call.data == 'get_deposit_address')
def handle_deposit_address_method(call):
    user_id = call.message.chat.id
    payment_currency = user_data[user_id]['payment_currency']
    deposit_wallet = VirtualAccountsTable.objects.get(user = user_id , currency=payment_currency)
    address = deposit_wallet.main_wallet_deposit_address
    account= MainWalletTable.objects.get(currency=payment_currency)
    account_id = account.virtual_account
    plan_price = float(user_data[user_id]['subscription_price'])
    img_byte_arr = generate_qr_code(address)
    plan_price = get_plan_price(payment_currency, plan_price)
    bot.send_photo(user_id, img_byte_arr, caption=f'You need to deposit {plan_price:.6f} amount. Please use the following '
                                                  f'address or scan the QR code to deposit balance: \n{address}')
    if account.subscription_id is None:
        subscription = create_subscription_v3(account_id, f'{os.getenv("webhook_url")}/{WEBHOOK_DEPOSIT}')
        subscription_data = subscription.json()
        account.subscription_id =subscription_data.get('id')
        account.save()

@csrf_exempt
@api_view(['GET', 'POST'])
def handle_deposit_webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": f"{INVALID_JSON}"}, status=400)

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
    balance = get_account_balance(account_id)
    if balance.status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR} \n{balance.json()}")
    balance_data = balance.json()
    available_balance = balance_data["availableBalance"]
    user_account.balance = available_balance
    user_account.save()
    user.subscription_status=f'{ACTIVE}'
    user.save()
    plan_id = user.plan
    print(f'plan id : {plan_id}')
    price = SubscriptionPlans.objects.get(plan_id= plan_id).plan_price

    if currency == f'{BTC}':
        btc_price = get_btc_price()
        price = convert_dollars_to_crypto(price, btc_price)


    elif currency == f'{ETH}':
        eth_price = get_eth_price()
        price = convert_dollars_to_crypto(price, eth_price)

    elif currency == f'{TRON}':
        tron_price = get_trx_price()
        price = convert_dollars_to_crypto(price, tron_price)

    elif currency == f'{LTC}':
        ltc_price = get_ltc_price()
        price = convert_dollars_to_crypto(price, ltc_price)

    if float(price) <= float(amount):
        bot.send_message(user_id, f"{DEPOSIT_ADDRESS}")
        set_subscription = set_user_subscription(user, plan_id )
        if set_subscription != f"{STATUS_CODE_200}":
            bot.send_message(user_id, set_subscription)

    else:
        bot.send_message(user_id, f"{INSUFFICIENT_DEPOSIT_AMOUNT}")
    return JsonResponse({"message": f"{WEBHOOK_RECEIVED}"}, status=200)


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
    bot.send_message(user_id, f"Top Up successful! ✅ ", reply_markup=get_main_menu())
    balance = get_account_balance(account_id)
    if balance.status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR} \n{balance.json()}")
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
        bot.send_message(message.chat.id, f"{PROCESSING_ERROR} {pathways.get('error')}")
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
        bot.send_message(user_id, f"{PROCESSING_ERROR} {pathway.get('error')}")
        return

    pathway_info = f"Name: {pathway.get('name')}\nDescription: {pathway.get('description')}\n\nNodes:\n" + \
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
        bot.send_message(message.chat.id, f"{PROCESSING_ERROR} {pathways.get('error')}")
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
                         "No IVR flows available!.\nPlease create a new IVR flow.",
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
        user_data[user_id]['first_node'] = True
        bot.send_message(user_id, f"IVR Flow '{pathway_name}' created! ✅ ")

        bot.send_message(user_id, f"Now, please select the language for this flow:", reply_markup=get_language_markup('flowlanguage'))

    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response}!", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_start_node')
def handle_add_start_node(message):
    user_id = message.chat.id
    message.text = 'End Call 🛑'
    add_node(message)


@bot.callback_query_handler(func=lambda call : call.data.startswith('flowlanguage:'))
def handle_add_flow_language(call):
    user_id = call.message.chat.id
    text = call.data
    lang = text.split(":")[1]
    user_data[user_id]['select_language'] = lang
    first_node = user_data[user_id]['first_node']
    if first_node:
        user_data[user_id]['message_type'] = 'Play Message'
        call.message.text = 'Play Message ▶️'
        user_data[user_id]['first_node'] = False
        bot.send_message(user_id, "Add your greeting node!")
        add_node(call.message)

    else:
        bot.send_message(user_id, "Select the type of node that you want to add: ", reply_markup=get_node_menu())

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'show_error_node_type')
def handle_show_error_node_type(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select from the menu provided below:", reply_markup=get_node_menu())


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'get_batch_numbers',
                     content_types=['text', 'document'])
def get_batch_call_base_prompt(message):
    user_id = message.chat.id
    pathway_id = user_data[user_id]['call_flow_bulk']

    subscription_details = UserSubscription.objects.get(user_id=user_id)
    max_contacts = subscription_details.bulk_ivr_calls_left
    if max_contacts > 50:
        max_contacts = 50
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
            bot.send_message(user_id, f"{PROCESSING_ERROR} {str(e)}", reply_markup=get_main_menu())

            return
    calls_sent = len(base_prompts)

    if calls_sent > max_contacts:
        bot.send_message(user_id,
                         f"Only {max_contacts} calls are allowed. You provided {calls_sent}. "
                         f"Please reduce the number of contacts and try again.", reply_markup=get_main_menu())
        return
    if calls_sent == 0:
        bot.send_message(user_id,"Your subscription plan has expired!", reply_markup=get_main_menu())
        return

    formatted_prompts = [{"phone_number": phone} for phone in base_prompts if phone]

    user_data[user_id]['base_prompts'] = formatted_prompts
    user_data[user_id]['step'] = 'batch_numbers'

    response = bulk_ivr_flow(formatted_prompts, pathway_id)

    if response.status_code == 200:
        bot.send_message(user_id, "Successfully sent!", reply_markup=get_main_menu())
        subscription_details.bulk_ivr_calls_left = subscription_details.bulk_ivr_calls_left - calls_sent
        subscription_details.save()

    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response.text}", reply_markup=get_main_menu())



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
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response}!", reply_markup=get_main_menu())


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

        user_data[user_id]['call_flow'] = pathway_id
        user_data[user_id]['step'] = 'initiate_call'
        bot.send_message(user_id, "Please enter the phone number to call (include country code).")
    elif step == 'get_batch_numbers':
        user_data[user_id]['call_flow_bulk'] = pathway_id
        bot.send_message(user_id, "Please paste phone numbers (with country codes) or upload a file (TXT or CSV "
                                  "format) with up to 50 phone numbers.")


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'add_edges')
def handle_add_edges(message):
    chat_id = message.chat.id
    pathway = Pathways.objects.get(pathway_name=user_data[chat_id]['pathway_name'])
    pathway_id = pathway.pathway_id
    response, status = handle_view_single_flow(pathway_id)

    if status != 200:
        bot.send_message(chat_id, f"{PROCESSING_ERROR} {response}", reply_markup=get_main_menu())
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


@bot.message_handler(func=lambda message: 'step' in user_data.get(message.chat.id, {}) and user_data[message.chat.id]['step'] == 'add_label')
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

        # Reset user state
        if message.text not in edges_complete:
            user_data[chat_id]['step'] = 'error_edges_complete'
    else:
        bot.send_message(chat_id, f"{PROCESSING_ERROR} {response}")


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

        if text in node_ids:
            bot.send_message(user_id, "This number has already been assigned to another node. Please enter a different number.")
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
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response}")


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

    if message_type == 'Transfer Call':
        if not validate_transfer_number(text):
            bot.send_message(user_id,
                             "Invalid number! Please enter a valid phone number with country code (e.g., +1234567890).")
            return

    response = handle_dtmf_input_node(pathway_id, node_id, prompt, node_name, message_type)

    if response.status_code == 200:
        bot.send_message(user_id, f"Node '{node_name}' with '{message_type}' added successfully! ✅",
                         reply_markup=get_node_complete_menu())
        if message.text not in node_complete:
            user_data[user_id]['step'] = 'error_nodes_complete'
    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response}")


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
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response}")


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
    bot.send_message(user_id, f"{PROCESSING_ERROR} {response}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("language:"))
def handle_language_selection(call):
    user_id = call.from_user.id
    selected_language = call.data.split(":")[1]
    user_data[user_id] = {'language': selected_language, 'step': 'terms_and_conditions'}
    bot.send_message(user_id,
                     f"You have selected {selected_language}.")
    user = TelegramUser.objects.get(user_id = user_id)
    user.language = selected_language
    user.save()
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
    handle_activate_subscription(call)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_language")
def handle_back_to_language(call):
    signup(call.message)


def send_confirmation_menu(user_id):
    if 'first_time' not in user_data.get(user_id, {}):
        user_data[user_id]['first_time'] = False
        bot.send_message(user_id, "Welcome! 🎉 You have one free Single IVR call and Bulk IVR "
                                  "call as a welcome gift. ☎️ ", reply_markup=get_main_menu())
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
