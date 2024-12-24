import base64
from io import BytesIO
import phonenumbers
from PIL import Image
import json
from uuid import UUID
import re
import io
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from phonenumbers import geocoder


import bot.bot_config
from TelegramBot.constants import STATUS_CODE_200, MAX_INFINITY_CONSTANT
from payment.decorator_functions import check_validity, check_subscription_status

from translations.translations import *  # noqa

from bot.models import (
    Pathways,
    TransferCallNumbers,
    FeedbackLogs,
    CallLogsTable,
    CallDuration,
)

from bot.utils import (
    generate_random_id,
    username_formating,
    convert_crypto_to_usd,
    validate_edges,
    get_currency,
    set_user_subscription,
    set_plan,
    set_details_for_user_table,
    get_plan_price,
    get_user_language,
    reset_user_language,
)

from bot.views import (
    handle_create_flow,
    handle_view_flows,
    handle_delete_flow,
    handle_add_node,
    play_message,
    handle_view_single_flow,
    handle_dtmf_input_node,
    handle_menu_node,
    send_call_through_pathway,
    empty_nodes,
    bulk_ivr_flow,
    get_transcript,
    question_type,
    get_variables,
    check_pathway_block,
)

from payment.models import SubscriptionPlans
from payment.views import (
    setup_user,
    check_user_balance,
    create_crypto_payment,
    credit_wallet_balance,
)

from user.models import TelegramUser
from bot.keyboard_menus import *  # noqa
from bot.bot_config import *  # noqa

from bot.callback_query_handlers import *  # noqa

VALID_NODE_TYPES = [
    "End Call 🛑",
    "Call Transfer 🔄",
    "Get DTMF Input 📞",
    "Play Message ▶️",
    "Menu 📋",
    "Feedback Node",
    "Question",
]
available_commands = {
    "/create_flow": "Create a new pathway",
    "/view_flows": "Get all pathways",
    "/add_node": "Add a node to the pathway",
}
webhook_url = os.getenv("webhook_url")


call_data = []
TERMS_AND_CONDITIONS_URL = os.getenv("TERMS_AND_CONDITIONS_URL")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")

# :: TRIGGERS ------------------------------------#


@bot.message_handler(func=lambda message: message.text == "Join Channel 🔗")
def handle_join_channel(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        f"{JOIN_CHANNEL_PROMPT[lg]}\n {CHANNEL_LINK}",
        reply_markup=support_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "Profile 👤")
def get_user_profile(message):
    user_id = message.chat.id
    user = TelegramUser.objects.get(user_id=message.chat.id)
    lg = get_user_language(user_id)
    bot.send_message(user_id, f"{PROFILE_INFORMATION_PROMPT[lg]}")
    username_formated = user.user_name.replace("_", "\\_")
    bot.send_message(
        user_id, f"{USERNAME[lg]} : {username_formated}", parse_mode="Markdownv2"
    )
    if user.subscription_status == f"{INACTIVE}":
        bot.send_message(user_id, f"{NO_SUBSCRIPTION_PLAN[lg]}")
    else:
        user_plan = UserSubscription.objects.get(user_id=user.user_id)
        plan_msg = (
            f"{SUBSCRIPTION_PLAN[lg]}: \n"
            f"{NAME[lg]} :{user_plan.plan_id.name}\n"
            f"{BULK_IVR_LEFT[lg]} : {user_plan.bulk_ivr_calls_left}\n"
        )
        if user_plan.single_ivr_left != MAX_INFINITY_CONSTANT:
            plan_msg += f"{SINGLE_CALLS_LEFT[lg]}{user_plan.single_ivr_left}\n"
        bot.send_message(user_id, plan_msg)
        wallet = check_user_balance(user_id)
        balance = wallet.json()["data"]["amount"]
        bot.send_message(
            user_id, f"{BALANCE_IN_USD[lg]}{balance}", reply_markup=account_keyboard()
        )
        bot.send_message(
            user_id,
            SELECTION_PROMPT[lg],
            reply_markup=account_keyboard(),
        )


@bot.message_handler(func=lambda message: message.text == "Back 📞")
def handle_back_ivr_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, FLOW_OPERATIONS_SELECTION_PROMPT[lg], reply_markup=ivr_flow_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "Back 📲")
def handle_back_ivr_call(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, FLOW_OPERATIONS_SELECTION_PROMPT[lg], reply_markup=ivr_call_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "Help ℹ️")
def handle_help(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, f"{AVAILABLE_COMMANDS_PROMPT[lg]}", reply_markup=support_keyboard()
    )


@bot.message_handler(commands=["help"])
def show_available_commands(message):
    handle_help(message)


@bot.message_handler(func=lambda message: message.text == "Bulk IVR Call 📞📞")
@check_validity
def trigger_bulk_ivr_call(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user = TelegramUser.objects.get(user_id=user_id)
    if user.subscription_status == "active":
        additional_minutes_records = CallDuration.objects.filter(
            user_id=user_id, additional_minutes__gt=0
        )
        if additional_minutes_records.exists():
            unpaid_minutes_records = additional_minutes_records.filter(charged=False)
            if unpaid_minutes_records.exists():
                bot.send_message(
                    user_id,
                    f"{UNPAID_MINUTES_PROMPT[lg]}",
                    reply_markup=get_main_menu_keyboard(),
                )
                return
        user_data[user_id] = {"step": "get_batch_numbers"}
        view_flows(message)
    else:
        bot.send_message(
            user_id,
            f"{BULK_IVR_SUBSCRIPTION_PROMPT[lg]}",
            reply_markup=get_subscription_activation_markup(),
        )


@bot.callback_query_handler(func=lambda call: call.data == "help")
def handle_help_callback(call):
    handle_help(call.message)


@bot.message_handler(func=lambda message: message.text == "Billing and Subscription 📅")
def trigger_billing_and_subscription(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        f"{SELECTION_PROMPT[lg]}",
        reply_markup=get_billing_and_subscription_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "Settings ⚙")
def trigger_settings(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, SELECTION_PROMPT[lg], reply_markup=get_setting_keyboard())


@bot.callback_query_handler(func=lambda call: call.data == "change_language")
def handle_change_user_language(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        UPDATE_LANGUAGE_PROMPT[lg],
        reply_markup=get_language_markup("updatelanguage"),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("updatelanguage:"))
def handle_language_selection(call):
    user_id = call.from_user.id
    selected_language = call.data.split(":")[1]
    print("language : ", {selected_language})
    user = TelegramUser.objects.get(user_id=user_id)
    user.language = selected_language
    user.save()
    if user_id not in user_data:
        user_data[user_id] = {}
    reset_user_language(user_id)
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, LANGUAGE_CHANGED_SUCCESSFULLY[lg], reply_markup=get_setting_keyboard()
    )


@bot.callback_query_handler(func=lambda call: call.data == "view_subscription")
@check_subscription_status
def handle_view_subscription(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    try:
        user = TelegramUser.objects.get(user_id=user_id)
        plan = user.plan

        subscription_plan = SubscriptionPlans.objects.get(plan_id=plan)
        if subscription_plan.single_ivr_minutes == MAX_INFINITY_CONSTANT:
            single_calls = f"{UNLIMITED_SINGLE_IVR[lg]}"
        else:
            single_calls = (
                f"{subscription_plan.single_ivr_minutes:.4f} {SINGLE_IVR_MINUTES[lg]}"
            )

        plan_details = (
            f"{PLAN_NAME[lg]} {subscription_plan.name}\n"
            f"{PRICE[lg]} ${subscription_plan.plan_price}\n\n"
            f"{FEATURES[lg]}\n"
            f"- '{single_calls}'\n"
            f"- {subscription_plan.number_of_bulk_call_minutes:.2f} {BULK_IVR_CALLS[lg]}\n"
            f"- {subscription_plan.customer_support_level} {CUSTOMER_SUPPORT_LEVEL[lg]}\n"
            f"- {subscription_plan.validity_days} {DAY_PLAN[lg]}\n"
        )

        if subscription_plan.call_transfer:
            plan_details += f"{FULL_NODE_ACCESS[lg]} : {CALL_TRANSFER_INCLUDED[lg]}"
        else:
            plan_details += f"{FULL_NODE_ACCESS[lg]} : {CALL_TRANSFER_EXCLUDED[lg]}"

        bot.send_message(
            user_id,
            f"{ACTIVE_SUBSCRIPTION_PLAN_PROMPT[lg]}\n\n{plan_details}",
            reply_markup=get_billing_and_subscription_keyboard(),
        )

    except TelegramUser.DoesNotExist:
        bot.send_message(
            user_id,
            f"{SUBSCRIPTION_PLAN_NOT_FOUND[lg]}",
            reply_markup=get_billing_and_subscription_keyboard(),
        )

    except SubscriptionPlans.DoesNotExist:
        bot.send_message(
            user_id,
            f"{NO_SUBSCRIPTION_PLAN[lg]}",
            reply_markup=get_billing_and_subscription_keyboard(),
        )


@bot.callback_query_handler(func=lambda call: call.data == "update_subscription")
def update_subscription(call):
    user_id = call.message.chat.id
    if user_id not in user_data:
        user_data[user_id] = {"step": None}
    user_data[user_id]["step"] = "update_subscription"
    handle_activate_subscription(call)


def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)


@bot.callback_query_handler(func=lambda call: call.data == "check_wallet")
def check_wallet(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, escape_markdown(f"{CHECKING_WALLETS[lg]}"), parse_mode="MarkdownV2"
    )
    try:
        wallet = check_user_balance(user_id)
        if wallet.status_code != 200:
            bot.send_message(user_id, f"{WALLET_DETAILS_ERROR[lg]} {wallet.text}")
        balance = wallet.json()["data"]["amount"]
        currency = wallet.json()["data"]["currency"]
        markup = InlineKeyboardMarkup()
        top_up_wallet_button = types.InlineKeyboardButton(
            "Top Up Wallet 💳", callback_data="top_up_wallet"
        )
        back_button = types.InlineKeyboardButton(
            "Back", callback_data="back_to_billing"
        )
        markup.add(top_up_wallet_button)
        markup.add(back_button)
        bot.send_message(
            user_id, f"{WALLET_BALANCE[lg]}\n{balance} {currency}", reply_markup=markup
        )
    except Exception as e:
        bot.send_message(
            user_id,
            escape_markdown(f"{PROCESSING_ERROR[lg]}\n\n{str(e)}"),
            parse_mode="MarkdownV2",
        )
    return


@bot.callback_query_handler(func=lambda call: call.data == "back_to_billing")
def back_to_billing(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        f"{SELECTION_PROMPT[lg]}",
        reply_markup=get_billing_and_subscription_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "Add Another Phone Numbers")
def trigger_yes(message):
    user_id = message.chat.id
    number = user_data[user_id]["batch_numbers"]
    data = {"phone_number": f"{number}"}
    call_data.append(data)


@bot.message_handler(func=lambda message: message.text == "Text-to-Speech 🗣️")
def trigger_text_to_speech(message):
    handle_get_node_type(message)


@bot.message_handler(func=lambda message: message.text == "Single IVR Call ☎️")
@check_validity
def trigger_single_ivr_call(message):
    """
    Handles the 'Single IVR Call ☎️' menu option to initiate an IVR call.

    Args:
       message: The message object from the user.
    """
    user_id = message.from_user.id
    user = TelegramUser.objects.get(user_id=user_id)
    lg = get_user_language(user_id)

    if user.subscription_status == "active":
        bot.send_message(user_id, SUBSCRIPTION_VERIFIED[lg])
        user_data[user_id] = {"step": "phone_number_input"}
        view_flows(message)

    else:
        bot.send_message(
            user_id,
            f"{ACTIVATE_SUBSCRIPTION[lg]}",
            reply_markup=get_subscription_activation_markup(),
        )


@bot.callback_query_handler(func=lambda call: call.data == "trigger_single_flow")
def trigger_flow_single(call):
    user_id = call.message.chat.id
    user_data[user_id] = {"step": "phone_number_input"}
    view_flows(call.message)


@bot.message_handler(func=lambda message: message.text == "Back")
def trigger_back_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    step = user_data[user_id]["step"]
    if step == "display_flows":
        display_flows(message)
        return
    bot.send_message(
        user_id, f"{WELCOME_PROMPT[lg]}", reply_markup=get_main_menu_keyboard()
    )


@bot.message_handler(
    func=lambda message: message.text == "Done Adding Nodes"
    or message.text == "Continue Adding Edges ▶️"
)
def trigger_add_edges(message):
    """
    Handles the 'Done Adding Nodes' menu option to initiate edge addition.

    Args:
        message: The message object from the user.
    """
    handle_add_edges(message)


@bot.message_handler(func=lambda message: message.text == "Confirm Delete")
def trigger_confirmation(message):
    """
    Handles the 'Confirm Delete' menu option to confirm deletion of a pathway.
    Args:
        message: The message object from the user.
    """
    handle_get_pathway(message)


@bot.message_handler(func=lambda message: message.text == "Delete Node")
def trigger_delete_node(message):
    """
    Handles the 'Delete Node' menu option. Placeholder for future functionality.

    Args:
        message: The message object from the user.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    pathway_id = user_data[user_id]["view_pathway"]
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    user_data[user_id]["pathway_name"] = pathway.pathway_name
    pathway, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {pathway.get('error')}")
        return
    keyboard = InlineKeyboardMarkup()

    for node in pathway["nodes"]:
        node_name = node["data"]["name"]
        button = InlineKeyboardButton(
            text=node_name, callback_data=f"delete_node_{node_name}"
        )
        keyboard.add(button)
    bot.send_message(user_id, f"{SELECTION_PROMPT[lg]}", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_node_"))
def delete_node(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    node_name = call.data.replace("delete_node_", "")
    pathway_id = user_data[user_id]["view_pathway"]
    try:
        pathway = Pathways.objects.get(pathway_id=pathway_id)
    except Pathways.DoesNotExist:
        bot.send_message(user_id, f"{PATHWAY_NOT_FOUND[lg]}")
        return
    pathway_payload = json.loads(pathway.pathway_payload)
    nodes = pathway_payload["pathway_data"]["nodes"]
    node_id_to_delete = None
    for node in nodes:
        if node["data"]["name"] == node_name:
            node_id_to_delete = node["id"]
            break
    if not node_id_to_delete:
        bot.send_message(user_id, f"{node_name} {NOT_FOUND[lg]}")
        return
    new_nodes = [node for node in nodes if node["id"] != node_id_to_delete]
    edges = pathway_payload["pathway_data"]["edges"]
    new_edges = [
        edge
        for edge in edges
        if edge["source"] != node_id_to_delete and edge["target"] != node_id_to_delete
    ]
    pathway_payload["pathway_data"]["nodes"] = new_nodes
    pathway_payload["pathway_data"]["edges"] = new_edges
    pathway.pathway_payload = json.dumps(pathway_payload)
    data = {
        "name": pathway_payload["pathway_data"]["name"],
        "description": pathway_payload["pathway_data"]["description"],
        "nodes": new_nodes,
        "edges": new_edges,
    }

    updated = handle_add_node(pathway_id, data)

    if updated.status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]}\n" f"{updated.text}")
        return

    pathway.pathway_payload = updated.text
    pathway.save()
    bot.send_message(user_id, f"{node_name} {EDGES_DELETED[lg]}")
    user_data[user_id]["step"] = "delete_node"


@bot.message_handler(func=lambda message: message.text == "Retry Node 🔄")
def trigger_retry_node(message):
    """
    Handles the 'Retry Node 🔄' menu option to retry a node.

    Args:
        message: The message object from the user.
    """
    bot.send_message(message.chat.id, "Retry node")


@bot.message_handler(func=lambda message: message.text == "Skip Node ⏭️")
def trigger_skip_node(message):
    """
    Handles the 'Skip Node ⏭️' menu option to skip a node.

    Args:
       message: The message object from the user.
    """
    bot.send_message(message.chat.id, "Skip node")


@bot.message_handler(func=lambda message: message.text == "Transfer to Live Agent 👤")
def trigger_transfer_to_live_agent_node(message):
    transfer_to_agent(message)


@bot.message_handler(func=lambda message: message.text == "Done Adding Edges")
def trigger_end_call_option(message):
    chat_id = message.chat.id
    lg = get_user_language(chat_id)
    pathway_id = user_data[chat_id]["select_pathway"]
    response, status_code = handle_view_single_flow(pathway_id)

    # Validate edges
    validation_result = validate_edges(response)
    missing_sources = validation_result["missing_sources"]
    missing_targets = validation_result["missing_targets"]
    valid = validation_result["valid"]

    if not valid:
        if missing_sources:
            bot.send_message(
                chat_id,
                f"{OUTGOING_CONNECTIONS_MISSING[lg]}" f"{', '.join(missing_sources)}",
            )
        if missing_targets:
            bot.send_message(
                chat_id,
                f"{INCOMING_CONNECTIONS_MISSING[lg]}{', '.join(missing_targets)}",
            )
        bot.send_message(chat_id, ADD_ONE_EDGE[lg])
        handle_add_edges(message)
    else:
        handle_call_failure(message)


@bot.message_handler(func=lambda message: message.text == "Continue to Next Node ▶️")
def trigger_add_another_node(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    keyboard = check_user_has_active_free_plan(user_id)
    bot.send_message(
        message.chat.id, f"{NODE_TYPE_SELECTION_PROMPT[lg]}", reply_markup=keyboard
    )


@bot.message_handler(func=lambda message: message.text == "Repeat Message 🔁")
def trigger_repeat_message(message):
    pass


@bot.message_handler(
    func=lambda message: message.text == "Back to Main Menu ↩️"
    or message.text == "Back ↩️"
)
def trigger_back(message):
    user_id = message.chat.id
    try:
        if user_data[user_id]["step"] == "back_delete_flow":
            delete_flow(message)
        else:
            send_welcome(message)
    except KeyError:
        send_welcome(message)


@bot.message_handler(
    func=lambda message: message.text == "End Call 🛑"
    or message.text == "Call Transfer 🔄"
    or message.text == "Get DTMF Input 📞"
    or message.text == "Play Message ▶️"
    or message.text == "Menu 📋"
    or message.text == "Feedback Node"
    or message.text == "Question"
)
def trigger_main_add_node(message):
    add_node(message)


@bot.message_handler(func=lambda message: message.text == "View Variables")
def view_variables(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    list_calls = CallLogsTable.objects.filter(user_id=user_id)

    if not list_calls.exists():
        bot.send_message(user_id, f"{CALL_LOGS_NOT_FOUND[lg]}")
        return
    markup = types.InlineKeyboardMarkup()

    for call in list_calls:
        button_text = f"Call ID: {call.call_id}"
        callback_data = f"variables_{call.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    bot.send_message(user_id, f"{VIEW_VARIABLES_PROMPT[lg]}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("variables_"))
def handle_call_selection_variable(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    try:
        call_id = call.data[len("variables_") :]
        variables = get_variables(call_id)
        if variables is None:
            msg = f"{NO_VARIABLES_FOUND[lg]} {call_id}"
            bot.send_message(user_id, escape_markdown(msg), parse_mode="MarkdownV2")
            return
        formatted_variables = []
        for key, value in variables.items():
            formatted_key = key.replace("_", "\\_")
            formatted_variables.append(f"{formatted_key}: {value}")
        variable_message = "\n".join(formatted_variables)

        if not variable_message:
            msg = f"{NO_VARIABLES_FOUND[lg]} {call_id}"
            bot.send_message(user_id, escape_markdown(msg), parse_mode="MarkdownV2")
        else:
            bot.send_message(user_id, variable_message, parse_mode="MarkdownV2")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"{PROCESSING_ERROR[lg]} {str(e)}")


@bot.message_handler(func=lambda message: message.text == "User Feedback")
def view_feedback(message):

    user_id = message.chat.id
    lg = get_user_language(user_id)
    feedback_pathway_ids = FeedbackLogs.objects.values_list("pathway_id", flat=True)
    list_calls = CallLogsTable.objects.filter(
        user_id=user_id, pathway_id__in=feedback_pathway_ids
    )
    if not list_calls.exists():
        bot.send_message(user_id, f"{CALL_LOGS_NOT_FOUND[lg]}")
        return
    markup = types.InlineKeyboardMarkup()
    for call in list_calls:
        button_text = f"Call ID: {call.call_id}"
        callback_data = f"feedback_{call.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    markup.add(types.InlineKeyboardButton("Back ↩️", callback_data="back_account"))

    bot.send_message(user_id, f"{VIEW_TRANSCRIPT_PROMPT[lg]}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("feedback_"))
def handle_call_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    try:
        call_id = call.data[len("feedback_") :]
        call_log = CallLogsTable.objects.get(call_id=call_id)
        pathway_id = call_log.pathway_id
        transcript = get_transcript(call_id, pathway_id)
        if transcript:
            transcript_message = "\n".join(
                f"Q: {question}\nA: {answer}"
                for question, answer in zip(
                    transcript.feedback_questions, transcript.feedback_answers
                )
            )
        else:
            transcript_message = f"{TRANSCRIPT_NOT_FOUND[lg]}"
        bot.send_message(user_id, transcript_message)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"{PROCESSING_ERROR[lg]} {str(e)}")


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
    lg = get_user_language(user_id)
    user_data[user_id]["first_node"] = False
    bot.send_message(
        user_id,
        f"{LANGUAGE_SELECTION_PROMPT[lg]}",
        reply_markup=get_language_markup("flowlanguage"),
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "select_node"
)
def select_node(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user_data[user_id]["select_language"] = message.text
    keyboard = check_user_has_active_free_plan(user_id)
    bot.send_message(
        user_id, f"{NODE_TYPE_SELECTION_PROMPT[lg]}", reply_markup=keyboard
    )


# :: BOT MESSAGE HANDLERS FOR FUNCTIONS ------------------------------------#


def send_welcome(message):
    """
    Sends a welcome message when the user starts a conversation.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, f"{WELCOME_PROMPT[lg]}", reply_markup=get_main_menu_keyboard()
    )


@bot.message_handler(commands=["help"])
def show_commands(message):
    """
    Handle '/help' command to show available commands.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    formatted_commands = "\n".join(
        [
            f"{command} - {description}"
            for command, description in available_commands.items()
        ]
    )
    bot.send_message(
        message.chat.id,
        f"{AVAILABLE_COMMANDS_PROMPT[lg]}\n{formatted_commands}",
        reply_markup=get_main_menu_keyboard(),
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "profile_language"
)
def get_profile_language(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    name = message.text
    username = username_formating(name)
    username = f"{username}_{user_id}"
    user_data[user_id] = {"step": "get_email", "name": name, "username": username}
    bot.send_message(
        user_id, f"{NICE_TO_MEET_YOU[lg]}!😊 {name}, " f"{PROFILE_SETTING_PROMPT[lg]}⏳"
    )
    bot.send_message(user_id, EMAIL_PROMPT[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "get_email"
)
def get_email(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    email = message.text
    if not validate_email(email):
        bot.send_message(
            user_id, INVALID_EMAIL_FORMAT[lg], reply_markup=get_force_reply()
        )
        return
    user_data[user_id]["email"] = email
    user_data[user_id]["step"] = "get_mobile"
    bot.send_message(user_id, MOBILE_NUMBER_PROMPT[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "get_mobile"
)
def get_mobile(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    mobile = message.text
    if not validate_mobile(mobile):
        bot.send_message(
            user_id, INVALID_NUMBER_PROMPT[lg], reply_markup=get_force_reply()
        )
        return
    name = user_data[user_id]["name"]
    username = user_data[user_id]["username"]
    email = user_data[user_id]["email"]
    response = setup_user(user_id, email, mobile, name, username)
    if response["status"] != 200:
        if response["status"] == 503:
            bot.send_message(
                user_id,
                "Account is already taken! Try it with a different email address!",
                reply_markup=get_force_reply(),
            )
            user_data[user_id]["step"] = "get_email"
            return
        else:
            bot.send_message(user_id, f"{REQUEST_FAILED[lg]}\n{response['text']}")
    else:
        bot.send_message(user_id, f"🎉 {SETUP_COMPLETE[lg]}")
        user_data[user_id]["step"] = ""
        handle_terms_and_conditions(message)


def validate_email(email):
    email_regex = (
        r"^(?![.-])([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}$"
    )
    return re.match(email_regex, email) is not None


def validate_mobile(mobile):
    try:
        number = phonenumbers.parse(mobile)
        region = geocoder.region_code_for_number(number)
        is_valid = phonenumbers.is_valid_number(number)
        print(f"Parsed Number: {mobile}, Region: {region}, Valid: {is_valid}")
        if not is_valid:
            print(f"Number {mobile} is invalid based on region-specific rules.")
            return False
        return True
    except phonenumbers.phonenumberutil.NumberParseException as e:
        print(f"Error parsing number {mobile}: {e}")
        return False


@bot.message_handler(commands=["cancel"])
def cancel_actions(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    msg = f"{ACTION_CANCELLED[lg]}\n{MAIN_MENU_REDIRECTION[lg]}"
    bot.send_message(user_id, msg, reply_markup=get_main_menu_keyboard())


@bot.message_handler(commands=["support"])
def display_support_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, SELECTION_PROMPT[lg], reply_markup=support_keyboard())


def display_main_menu(message):
    user_id = message.chat.id
    bot.send_message(
        user_id, "Welcome to the main menu!", reply_markup=get_main_menu_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "IVR Flow 📞")
def display_ivr_flow_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, FLOW_OPERATIONS_SELECTION_PROMPT[lg], reply_markup=ivr_flow_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "IVR Calls 📲")
def display_ivr_calls_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, IVR_CALL_SELECTION_PROMPT[lg], reply_markup=ivr_call_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "Account 👤")
def display_account_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, SELECTION_PROMPT[lg], reply_markup=account_keyboard())


@bot.message_handler(commands=["sign_up", "start"])
def language_selection(message):
    user_id = message.chat.id
    try:
        existing_user, created = TelegramUser.objects.get_or_create(
            user_id=user_id, defaults={"user_name": f"{user_id}"}
        )
        if not created:
            lg = get_user_language(user_id)
            print(f"lg : {lg}")
            selected_language = existing_user.language
            print("user language: ", selected_language)
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]["set_language"] = selected_language
            bot.send_message(
                user_id,
                f"{EXISTING_USER_WELCOME[lg]}",
                reply_markup=get_main_menu_keyboard(),
            )
            return
        bot.send_message(
            user_id,
            f"🌍 {PROFILE_LANGUAGE_SELECTION_PROMPT['English']}",
            reply_markup=get_language_markup("language"),
        )
    except Exception as e:
        bot.reply_to(
            message, f"{PROCESSING_ERROR} {str(e)}", reply_markup=get_force_reply()
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_user_information"
)
def signup(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text if message.content_type == "text" else None
    bot.send_message(user_id, f"👋 **{SETUP_WELCOME[lg]}** \n" f"{SETUP_PROMPT[lg]}")
    setup_tooltip = escape_markdown(SETUP_TOOLTIP[lg])
    bot.send_message(user_id, f"_{setup_tooltip}_", parse_mode="MarkdownV2")

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "profile_language"
    name_input_prompt = escape_markdown(NAME_INPUT_PROMPT[lg])
    bot.send_message(user_id, f"👤 {name_input_prompt}", parse_mode="MarkdownV2")
    return


@bot.callback_query_handler(func=lambda call: call.data == "activate_subscription")
def handle_activate_subscription(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    plans = SubscriptionPlans.objects.all()
    plan_icons = {"Free": "🎉", "Prime": "🌟", "Elite": "💎", "Ultra": "🚀"}
    markup = types.InlineKeyboardMarkup()
    unique_plan_names = set()
    for plan in plans:
        plan_name_with_icon = f"{plan_icons.get(plan.name, '')} {plan.name}"
        if plan.name not in unique_plan_names:
            unique_plan_names.add(plan.name)
            plan_button = types.InlineKeyboardButton(
                plan_name_with_icon, callback_data=f"plan_name_{plan.name}"
            )
            markup.add(plan_button)
    back_button = types.InlineKeyboardButton(
        "Back ↩️", callback_data="back_to_view_terms"
    )
    markup.add(back_button)
    msg = f"💡 {SUBSCRIPTION_PLAN_OPTIONS[lg]}"
    bot.send_message(user_id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_view_terms")
def back_to_view_terms(call):
    user_id = call.message.chat.id
    if user_data[user_id]["step"] == "check_terms_and_conditions":
        view_terms_menu(call)
    else:
        trigger_billing_and_subscription(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_name_"))
def view_plan_validity(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    plan_name = call.data.split("_")[2]
    plans = SubscriptionPlans.objects.filter(name=plan_name).order_by("validity_days")
    plan_validity = {1: "1⃣", 7: "7⃣", 30: "📅"}
    message_text = f"🕒 {DURATION_SELECTION_PROMPT[lg]}"
    markup = types.InlineKeyboardMarkup()
    for plan in plans:
        if plan.validity_days == 1:
            day = f"{DAY[lg]}"
        else:
            day = f"{DAYS[lg]}"
        plan_icon = plan_validity.get(plan.validity_days, "")
        plan_button = types.InlineKeyboardButton(
            f"{plan_icon} {plan.validity_days} {day}",
            callback_data=f"plan_{plan.plan_id}",
        )
        markup.add(plan_button)
    back_button = types.InlineKeyboardButton(
        "Back ↩️", callback_data="back_to_plan_names"
    )
    markup.add(back_button)
    bot.send_message(user_id, f"{message_text}\n\n", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_plan_names")
def back_to_plan_names(call):
    handle_activate_subscription(call)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_welcome_message")
def handle_back_message(call):
    send_welcome(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def handle_plan_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    plan_id = call.data.split("_")[1]

    try:
        plan = SubscriptionPlans.objects.get(plan_id=plan_id)
    except SubscriptionPlans.DoesNotExist:
        bot.send_message(user_id, f"{PLAN_DOESNT_EXIST[lg]}")
        return

    if user_id not in user_data:
        user_data[user_id] = {}

    node_access = (
        f"{FULL_NODE_ACCESS[lg]}"
        if plan.call_transfer
        else f"{PARTIAL_NODE_ACCESS[lg]}"
    )
    call_transfer_node = "✅" if plan.call_transfer else "❌"

    user_data[user_id]["selected_plan"] = plan
    user_data[user_id]["subscription_price"] = plan.plan_price
    user_data[user_id]["subscription_name"] = plan.name
    user_data[user_id]["subscription_id"] = plan.plan_id
    if plan.single_ivr_minutes == MAX_INFINITY_CONSTANT:
        single_calls = f"{UNLIMITED_SINGLE_IVR[lg]}"
    else:
        single_calls = f"{plan.single_ivr_minutes:.4f} {SINGLE_IVR_MINUTES[lg]}"
    if plan.number_of_bulk_call_minutes is None:
        bulk_calls = NO_BULK_MINS_LEFT[lg]
    else:
        bulk_calls = f"{plan.number_of_bulk_call_minutes:.2f} {BULK_IVR_CALLS[lg]}"

    invoice_message = (
        f"{PLAN_SELECTED[lg]}\n"
        f"📌 {PLAN_NAME[lg]}  {plan.name}\n"
        f"🕛 {VALIDITY[lg]}   {plan.validity_days}"
        f"💲 {PRICE[lg]} {plan.plan_price:.2f}\n"
        f"📝 *{FEATURES[lg]}\n"
        f"🎧 {single_calls} & {bulk_calls}\n"
        f"🔗 {node_access}\n"
        f"📞 {CALL_TRANSFER_NODE[lg]} {call_transfer_node}\n"
        f"📞 {CUSTOMER_SUPPORT_LEVEL[lg]}: {plan.customer_support_level}\n\n"
    )

    if plan.plan_price == 0:
        bot.send_message(
            user_id, escape_markdown(invoice_message), parse_mode="MarkdownV2"
        )
        user = TelegramUser.objects.get(user_id=user_id)
        user.subscription_status = "active"
        user.plan = plan.plan_id
        user.save()
        set_subscription = set_user_subscription(user, plan.plan_id)
        if set_subscription != f"{STATUS_CODE_200}":
            bot.send_message(user_id, set_subscription)
            return
        bot.send_message(
            user_id,
            SUCCESSFUL_FREE_TRIAL_ACTIVATION[lg],
            reply_markup=get_main_menu_keyboard(),
        )
        return
    auto_renewal = escape_markdown(AUTO_RENEWAL_PROMPT[lg])
    yes = f"✅ Yes"
    no = f"❌ No"
    markup = types.InlineKeyboardMarkup()
    yes_button = types.InlineKeyboardButton(
        yes, callback_data="enable_auto_renewal_yes"
    )
    no_button = types.InlineKeyboardButton(no, callback_data="enable_auto_renewal_no")
    back_button = types.InlineKeyboardButton(
        "↩️ Back", callback_data="back_to_plan_names"
    )

    markup.add(yes_button, no_button)
    markup.add(back_button)
    invoice_message = escape_markdown(invoice_message)
    bot.send_message(
        user_id,
        f"{invoice_message} \n\n{auto_renewal}",
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )


@bot.callback_query_handler(
    func=lambda call: call.data in ["enable_auto_renewal_yes", "enable_auto_renewal_no"]
)
def handle_auto_renewal_choice(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    print(f"lg in handle auto_renewal {lg}")
    if call.data == "enable_auto_renewal_yes":
        user_data[user_id]["auto_renewal"] = True
        auto_renewal_enabled = f"{AUTO_RENEWAL_ENABLED[lg]}" f" {PROCEED_PAYMENT[lg]}"
        bot.send_message(user_id, auto_renewal_enabled)
    else:
        auto_renewal_disabled = f"{AUTO_RENEWAL_DISABLED[lg]} " f"{PROCEED_PAYMENT[lg]}"
        user_data[user_id]["auto_renewal"] = False
        bot.send_message(user_id, auto_renewal_disabled)
    send_payment_options(user_id)


@bot.callback_query_handler(func=lambda call: call.data == "payment_option")
def payment_option_callback(call):
    user_id = call.message.chat.id
    send_payment_options(user_id)


def insufficient_balance_markup():
    markup = types.InlineKeyboardMarkup()
    top_up_wallet_button = types.InlineKeyboardButton(
        "Top Up Wallet 💳", callback_data="top_up_wallet"
    )
    payment_option_btn = types.InlineKeyboardButton(
        "Choose Other Payment Option", callback_data="payment_option"
    )
    back_button = types.InlineKeyboardButton("Back", callback_data="back_to_billing")
    markup.add(top_up_wallet_button, payment_option_btn, back_button)
    return markup


def send_payment_options(user_id):
    lg = get_user_language(user_id)
    payment_message = f"💳 {SUBSCRIPTION_PAYMENT_METHOD_PROMPT[lg]}"
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    wallet_balance = f"💼 Pay from Wallet Balance"
    crypto = f"💰 Pay with Cryptocurrency"
    wallet_button = types.KeyboardButton(wallet_balance)
    crypto_button = types.KeyboardButton(crypto)
    markup.add(wallet_button, crypto_button)
    bot.send_message(user_id, payment_message, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "💼 Pay from Wallet Balance")
def payment_through_wallet_balance(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    amount = user_data[user_id]["subscription_price"]
    response = credit_wallet_balance(user_id, amount)
    if response.status_code != 200:
        msg = response.json().get("message")
        bot.send_message(
            user_id,
            f"{INSUFFICIENT_BALANCE[lg]}",
            reply_markup=insufficient_balance_markup(),
        )
        return
    plan_id = user_data[user_id]["subscription_id"]
    auto_renewal = user_data[user_id]["auto_renewal"]
    response = set_plan(user_id, plan_id, auto_renewal)
    if response["status"] != 200:
        bot.send_message(user_id, f"{response['message']}")
        return
    bot.send_message(
        user_id, PAYMENT_SUCCESSFUL[lg], reply_markup=get_main_menu_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "💰 Pay with Cryptocurrency")
def payment_through_cryptocurrency(message):
    user_id = message.chat.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["transaction_type"] = "payment"
    plan_id = user_data[user_id]["subscription_id"]
    response = set_details_for_user_table(user_id, plan_id)
    if response["status"] != 200:
        bot.send_message(user_id, f"{response['message']}")
        return
    currency_selection(user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def handle_payment_method(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    payment_method = call.data.split("_")[1]
    if payment_method == f"{back}":
        handle_activate_subscription(call)
        return
    currency_response = get_currency(payment_method)
    if currency_response != 200:
        bot.send_message(
            user_id, UNSUPPORTED_CURRENCY[lg], reply_markup=get_main_menu_keyboard()
        )
        return
    payment_currency = currency_response.text
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["payment_currency"] = payment_currency


@bot.callback_query_handler(func=lambda call: call.data == "back_to_handle_payment")
def handle_back_to_handle_payment(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        f"{SUBSCRIPTION_PAYMENT_METHOD_PROMPT[lg]}",
        reply_markup=get_currency_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "Top Up Wallet 💳")
def top_up_keyboard(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["topup_option_type"] = "keyboard"
    top_up(message)


def top_up(message):
    user_id = message.chat.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["transaction_type"] = "top_up"
    currency_selection(user_id)


@bot.callback_query_handler(func=lambda call: call.data == "top_up_wallet")
def handle_top_up_wallet(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["topup_option_type"] = "callback_query"
    top_up(call.message)


def currency_selection(user_id):
    lg = get_user_language(user_id)
    payment_methods = [
        "Bitcoin (BTC) ₿",
        "Ethereum (ETH) Ξ",
        "TRC-20 USDT 💵",
        "ERC-20 USDT 💵",
        "Litecoin (LTC) Ł",
        "DOGE (DOGE) Ɖ",
        "Bitcoin Hash (BCH) Ƀ",
        "TRON (TRX)",
        "Back ↩️",
    ]
    markup = types.InlineKeyboardMarkup()
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(
            method, callback_data=f"topup_{method}"
        )
        markup.add(payment_button)

    bot.send_message(user_id, f"{TOP_UP_PROMPT[lg]}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("topup_"))
def handle_account_topup(call):
    user_id = call.message.chat.id
    payment_method = call.data.split("_")[1]
    print(f"payment methoddd : {payment_method}")
    if payment_method == "Back ↩️":
        topup_type = user_data[user_id]["topup_option_type"]

        if topup_type == "callback_query":
            trigger_billing_and_subscription(call.message)
        else:
            send_welcome(call.message)
        return
    make_crypto_payment(user_id, payment_method)


def make_crypto_payment(user_id, payment_method):
    lg = get_user_language(user_id)
    response = get_currency(payment_method)
    if response["status"] != 200:
        bot.send_message(user_id, UNSUPPORTED_CURRENCY[lg])
        return
    payment_currency = response["text"]
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["currency"] = payment_currency
    user_data[user_id]["step"] = "get_amount"
    if user_data[user_id]["transaction_type"] == "top_up":
        bot.send_message(
            user_id, TOP_UP_AMOUNT_PROMPT[lg], reply_markup=get_force_reply()
        )
    else:
        amount = user_data[user_id]["subscription_price"]
        user_data[user_id]["amount"] = amount
        make_payment(user_id, amount)


def send_qr_code(
    user_id,
    address,
    crypto_amount,
    qr_code_base64=None,
):
    lg = get_user_language(user_id)

    if qr_code_base64:
        qr_code_data = qr_code_base64.split(",")[1]
        qr_code_image = base64.b64decode(qr_code_data)
        with BytesIO(qr_code_image) as qr_image:
            img = Image.open(qr_image)
            img.save("qr_code.png", "PNG")

    with open("qr_code.png", "rb") as img_file:
        bot.send_photo(
            user_id,
            img_file,
            caption=f"{SCAN_ADDRESS_PROMPT[lg]}",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
    payment_currency = user_data[user_id]["currency"]
    bot.send_message(
        user_id,
        f"{PART1_SCAN_PAYMENT_INFO[lg]} {crypto_amount} "
        f"{payment_currency} to <code>{address}</code>.\n\n"
        f"{PART3_SCAN_PAYMENT_INFO[lg]} "
        f"{PART4_SCAN_PAYMENT_INFO[lg]}\n\n"
        f"{PART5_SCAN_PAYMENT_INFO[lg]}\n"
        f"{PART6_SCAN_PAYMENT_INFO[lg]}",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )
    return


@csrf_exempt
def payment_deposit_webhook(request):
    if request.method == "POST":
        try:
            data = get_webhook_data(request)
            user_id = int(data["user_id"])
            lg = get_user_language(user_id)
            auto_renewal = data["auto_renewal"]
            amount = float(data["amount"])
            currency = data["currency"]
            bot.send_message(user_id, DEPOSIT_SUCCESSFUL[lg])
            plan_id = TelegramUser.objects.get(user_id=user_id).plan
            plan_price = float(
                SubscriptionPlans.objects.get(plan_id=plan_id).plan_price
            )  # Convert to float if necessary
            price_in_dollar = convert_crypto_to_usd(amount, currency)
            if plan_price > price_in_dollar:
                bot.send_message(
                    user_id,
                    f"{INSUFFICIENT_DEPOSIT_AMOUNT[lg]}\n"
                    f"{AMOUNT_NEEDED[lg]} {plan_price} USD\n"
                    f"{AMOUNT_DEPOSITED[lg]}{price_in_dollar} USD",
                )
                return JsonResponse(
                    {"status": "error", "message": "Insufficient amount"}, status=400
                )

            response = set_plan(user_id, plan_id, auto_renewal)
            if response["status"] != 200:
                bot.send_message(
                    user_id, f"{TABLE_UPDATE_FAILED[lg]}\n" f"{response['message']}"
                )
            return JsonResponse({"status": "success"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": INVALID_JSON}, status=400
            )
        except KeyError as e:
            return JsonResponse(
                {"status": "error", "message": f"{MISSING_KEY} key: {e}"}, status=400
            )
        except TypeError as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"status": "error", "message": METHOD_NOT_ALLOWED}, status=405)


def get_webhook_data(request):
    print(f"request body : {request.body}")
    data = json.loads(request.body)
    print("Received webhook data:", data)
    transaction_id = data.get("id")
    payment_status = data.get("status")
    meta_data = data.get("meta_data", {})
    user_id = meta_data.get("product_name")
    paid_amount = data.get("paid_amount")
    paid_currency = data.get("paid_currency")
    auto_renewal = meta_data.get("product")
    lg = get_user_language(user_id)

    message = (
        f"{TRANSACTION_ID[lg]} {transaction_id}\n"
        f"{PAYMENT_STATUS[lg]} {payment_status}\n"
        f"{USER_ID[lg]} {user_id}\n"
        f"{PAID_AMOUNT[lg]} {paid_amount}\n"
        f"{PAID_CURRENCY[lg]} {paid_currency}"
    )

    if auto_renewal == "True":
        auto_renewal = True
    else:
        auto_renewal = False
    bot.send_message(
        user_id,
        f"{TRANSACTION_DETAILS[lg]}\n{message}",
        reply_markup=get_main_menu_keyboard(),
    )
    return {
        "user_id": user_id,
        "auto_renewal": auto_renewal,
        "amount": paid_amount,
        "currency": paid_currency,
    }


@csrf_exempt
def crypto_transaction_webhook(request):
    if request.method == "POST":
        try:
            data = get_webhook_data(request)
            user_id = data["user_id"]
            lg = get_user_language(user_id)
            bot.send_message(user_id, TOP_UP_SUCCESSFUL[lg])
            return JsonResponse({"status": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": INVALID_JSON}, status=400
            )

    return JsonResponse({"status": "error", "message": METHOD_NOT_ALLOWED}, status=405)


def make_payment(user_id, amount):
    lg = get_user_language(user_id)
    currency = user_data[user_id]["currency"]
    top_up = False
    redirect_uri = f"{webhook_url}/webhook/crypto_deposit"
    auto_renewal = UserSubscription.objects.get(user_id=user_id).auto_renewal
    if user_data[user_id]["transaction_type"] == "top_up":
        top_up = True
        redirect_uri = f"{webhook_url}/webhook/crypto_transaction"
    crypto_payment = create_crypto_payment(
        user_id, amount, currency, redirect_uri, auto_renewal, top_up
    )
    print(f"make_crypto_payment response: {crypto_payment.text}")

    if crypto_payment.status_code != 200:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]}\n{crypto_payment.json()}")
        return
    response_data = crypto_payment.json().get("data", {})
    qr_code_base64 = response_data.get("qr_code")
    address = response_data.get("address")
    crypto_amount = response_data.get("crypto_amount")
    send_qr_code(user_id, address, crypto_amount, qr_code_base64)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "get_amount"
)
def get_top_up_amount(message):
    user_id = message.chat.id

    amount = message.text
    try:
        amount = float(amount)
        user_data[user_id]["amount"] = amount
    except ValueError:
        bot.send_message(
            user_id,
            "Amount should be a number. Please enter amount again: ",
            reply_markup=get_force_reply(),
        )
        user_data[user_id]["step"] = "get_amount"
        return

    make_payment(user_id, amount)


@bot.message_handler(commands=["create_flow"])
def create_flow(message):
    """
    Handle '/create_flow' command to initiate pathway creation.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user_data[user_id] = {"step": "ask_name"}
    bot.send_message(
        user_id, ENTER_PATHWAY_NAME_PROMPT[lg], reply_markup=get_force_reply()
    )


@bot.message_handler(commands=["delete_flow"])
def delete_flow(message):
    """
    Handle '/delete_flow' command to initiate pathway deletion.
    """
    user_id = message.chat.id
    user_data[user_id] = {"step": "get_pathway"}
    view_flows(message)


@bot.message_handler(commands=["add_node"])
def add_node(message):
    """
    Handle '/add_node' command to initiate node addition.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    pathway_name = user_data[user_id].get("pathway_name")
    pathway = Pathways.objects.get(pathway_name=pathway_name)
    user_data[user_id]["step"] = "add_node"
    user_data[user_id]["node"] = message.text
    user_data[user_id]["select_pathway"] = pathway.pathway_id
    bot.send_message(
        user_id, ENTER_CUSTOM_NODE_NAME[lg], reply_markup=get_force_reply()
    )


@bot.message_handler(commands=["view_flows"])
def display_flows(message):
    """
    Handle '/view_flows' command to retrieve all pathways.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    pathways, status_code = handle_view_flows()
    if status_code != 200:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {pathways.get('error')}",
            reply_markup=ivr_flow_keyboard(),
        )
        return

    current_users_pathways = Pathways.objects.filter(pathway_user_id=message.chat.id)
    user_pathway_ids = set(p.pathway_id for p in current_users_pathways)
    filtered_pathways = [
        pathway for pathway in pathways if pathway.get("id") in user_pathway_ids
    ]
    markup = InlineKeyboardMarkup()
    if filtered_pathways:
        pathway_buttons = [
            InlineKeyboardButton(
                pathway.get("name"), callback_data=f"view_pathway_{pathway.get('id')}"
            )
            for pathway in filtered_pathways
        ]
        markup.add(*pathway_buttons)
    markup.add(InlineKeyboardButton("Back ↩️", callback_data="back_ivr_flow"))
    bot.send_message(message.chat.id, DISPLAY_IVR_FLOWS[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_ivr_flow")
def trigger_back_ivr_flow(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, FLOW_OPERATIONS_SELECTION_PROMPT[lg], reply_markup=ivr_flow_keyboard()
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_ivr_call")
def trigger_back_ivr_call(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        IVR_CALL_SELECTION_PROMPT[lg],
        reply_markup=ivr_call_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_account")
def trigger_back_account(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, SELECTION_PROMPT[lg], reply_markup=account_keyboard())


@bot.callback_query_handler(func=lambda call: call.data == "back")
def handle_back_button(call):
    """
    Handle the 'Back ↩️' button callback.
    """
    trigger_back(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("view_pathway_"))
def handle_pathway_details(call):
    """
    Handle the display of a pathway details from the inline keyboard.
    """
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    pathway_id = call.data.split("_")[-1]
    pathway_id = UUID(pathway_id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]["view_pathway"] = pathway_id
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    user_data[user_id]["pathway_name"] = pathway.pathway_name
    pathway, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {pathway.get('error')}",
            reply_markup=ivr_flow_keyboard(),
        )
        return

    pathway_info = (
        f"{NAME[lg]}: {pathway.get('name')}\n"
        f"{DESCRIPTION[lg]}: {pathway.get('description')}\n\n"
    ) + "\n".join(
        [f"\n  {NAME[lg]}: {node['data']['name']}\n" for node in pathway["nodes"]]
    )
    user_data[user_id]["step"] = "display_flows"
    bot.send_message(user_id, pathway_info, reply_markup=get_flow_node_menu())


@bot.message_handler(commands=["list_flows"])
def view_flows(message):
    """
    Handle '/list_flows' command to retrieve all pathways.

    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    pathways, status_code = handle_view_flows()
    if status_code != 200:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {pathways.get('error')}",
            reply_markup=ivr_flow_keyboard(),
        )
        return
    step = user_data[user_id]["step"]

    current_users_pathways = Pathways.objects.filter(pathway_user_id=message.chat.id)
    user_pathway_ids = set(p.pathway_id for p in current_users_pathways)
    filtered_pathways = [
        pathway for pathway in pathways if pathway.get("id") in user_pathway_ids
    ]
    markup = InlineKeyboardMarkup()
    if filtered_pathways:
        pathway_buttons = [
            InlineKeyboardButton(
                pathway.get("name"), callback_data=f"select_pathway_{pathway.get('id')}"
            )
            for pathway in filtered_pathways
        ]
        markup.add(*pathway_buttons)
        markup.add(
            InlineKeyboardButton("Create IVR Flow ➕", callback_data="create_ivr_flow")
        )
        if step == "phone_number_input":
            callback = "back_ivr_call"
        else:
            callback = "back_ivr_flow"
        markup.add(InlineKeyboardButton("Back ↩️", callback_data=callback))
        bot.send_message(message.chat.id, SELECT_IVR_FLOW[lg], reply_markup=markup)
    else:
        markup.add(
            InlineKeyboardButton("Create IVR Flow ➕", callback_data="create_ivr_flow")
        )
        if step == "phone_number_input":
            callback = "back_ivr_call"
        else:
            callback = "back_ivr_flow"
        markup.add(InlineKeyboardButton("Back ↩️", callback_data=callback))
        bot.send_message(
            message.chat.id, NO_IVR_FLOW_AVAILABLE[lg], reply_markup=markup
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "ask_name"
)
def handle_ask_name(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text if message.content_type == "text" else None
    if Pathways.objects.filter(pathway_name=text).exists():
        bot.send_message(user_id, SIMILAR_FLOW_NAME_EXISTS[lg])
        return
    user_data[user_id]["pathway_name"] = text
    user_data[user_id]["step"] = "ask_description"
    bot.send_message(
        user_id, ENTER_PATHWAY_DESCRIPTION_PROMPT[lg], reply_markup=get_force_reply()
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "ask_description"
)
def handle_ask_description(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    user_data[user_id]["pathway_description"] = text
    pathway_name = user_data[user_id]["pathway_name"]
    pathway_description = user_data[user_id]["pathway_description"]
    response, status_code, pathway_id = handle_create_flow(
        pathway_name, pathway_description, user_id
    )

    if status_code == 200:
        res = empty_nodes(pathway_name, pathway_description, pathway_id)
        user_data[user_id]["first_node"] = True
        bot.send_message(user_id, f"'{pathway_name}' {FLOW_CREATED[lg]} ✅ ")

        bot.send_message(
            user_id,
            f"{LANGUAGE_SELECTION_FOR_FLOW[lg]}",
            reply_markup=get_language_markup("flowlanguage"),
        )

    else:
        keyboard = check_user_has_active_free_plan(user_id)
        bot.send_message(
            user_id, f"{PROCESSING_ERROR[lg]} {response}!", reply_markup=keyboard
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "add_start_node"
)
def handle_add_start_node(message):
    message.text = "End Call 🛑"
    add_node(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("flowlanguage:"))
def handle_add_flow_language(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    text = call.data
    lang = text.split(":")[1]
    user_data[user_id]["select_language"] = lang
    first_node = user_data[user_id]["first_node"]
    if first_node:
        user_data[user_id]["message_type"] = "Play Message"
        call.message.text = "Play Message ▶️"
        user_data[user_id]["first_node"] = False
        bot.send_message(user_id, ADD_GREETING_NODE[lg])
        add_node(call.message)

    else:
        keyboard = check_user_has_active_free_plan(user_id)
        bot.send_message(user_id, NODE_TYPE_SELECTION_PROMPT[lg], reply_markup=keyboard)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "show_error_node_type"
)
def handle_show_error_node_type(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    keyboard = check_user_has_active_free_plan(user_id)
    bot.send_message(user_id, MENU_SELECT[lg], reply_markup=keyboard)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_batch_numbers",
    content_types=["text", "document"],
)
def get_batch_call_base_prompt(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    pathway_id = user_data[user_id]["call_flow_bulk"]
    subscription_details = UserSubscription.objects.get(user_id=user_id)
    max_contacts = 50
    valid_phone_number_pattern = re.compile(r"^[\d\+\-\(\)\s]+$")
    base_prompts = []

    if message.content_type == "text":
        lines = message.text.split("\n")
        base_prompts = [
            line.strip()
            for line in lines
            if valid_phone_number_pattern.match(line.strip())
        ]

    elif message.content_type == "document":
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_stream = io.BytesIO(downloaded_file)
        try:
            content = file_stream.read().decode("utf-8")
            lines = content.split("\n")
            base_prompts = [
                line.strip()
                for line in lines
                if valid_phone_number_pattern.match(line.strip())
            ]
        except Exception as e:
            bot.send_message(
                user_id,
                f"{PROCESSING_ERROR[lg]} {str(e)}",
                reply_markup=get_main_menu_keyboard(),
            )

            return
    calls_sent = len(base_prompts)

    if calls_sent > max_contacts:
        bot.send_message(
            user_id,
            f"{max_contacts}{REDUCE_NUMBER_OF_CONTACTS[lg]}"
            f"{ALLOWED_CONTACTS_PROMPT[lg]}",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    if calls_sent == 0:
        bot.send_message(
            user_id, SUBSCRIPTION_EXPIRED[lg], reply_markup=get_main_menu_keyboard()
        )
        return

    formatted_prompts = [{"phone_number": phone} for phone in base_prompts if phone]

    user_data[user_id]["base_prompts"] = formatted_prompts
    user_data[user_id]["step"] = "batch_numbers"

    response = bulk_ivr_flow(formatted_prompts, pathway_id, user_id)

    if response.status_code == 200:
        bot.send_message(
            user_id, SUCCESSFULLY_SENT[lg], reply_markup=get_main_menu_keyboard()
        )

    else:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {response.text}",
            reply_markup=get_main_menu_keyboard(),
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "batch_numbers"
)
def get_batch_call_numbers(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user_data[user_id]["batch_numbers"] = message.text
    bot.message_handler(user_id, ADD_ANOTHER_NUMBER_PROMPT[lg])


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "get_pathway"
)
def handle_get_pathway(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    pathway_id = user_data[user_id]["select_pathway"]
    response, status_code = handle_delete_flow(pathway_id)

    if status_code == 200:
        bot.send_message(user_id, FLOW_DELETED_SUCCESSFULLY[lg])
        delete_flow(message)
    else:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {response}!",
            reply_markup=ivr_flow_keyboard(),
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_pathway_"))
def handle_pathway_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    pathway_id = call.data.split("_")[-1]
    pathway_id = UUID(pathway_id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]["select_pathway"] = pathway_id
    if not check_pathway_block(str(pathway_id)):
        bot.send_message(user_id, NO_BLOCKS[lg])
        view_flows(call.message)
        return
    if "step" in user_data.get(user_id, {}):
        step = user_data[user_id]["step"]
    else:
        step = None
    if step is None:
        user_data[user_id]["step"] = "add_node"
        bot.send_message(
            user_id, ENTER_CUSTOM_NODE_NAME[lg], reply_markup=get_force_reply()
        )
    elif step == "get_pathway":
        user_data[user_id]["step"] = "back_delete_flow"
        bot.send_message(
            user_id,
            DELETE_FLOW_CONFIRMATION[lg],
            reply_markup=get_delete_confirmation_keyboard(),
        )
    elif step == "phone_number_input":
        print("phone numbers ")
        user_data[user_id]["call_flow"] = pathway_id
        user_data[user_id]["step"] = "initiate_call"
        msg = f"{ENTER_PHONE_NUMBER_PROMPT[lg]}:"
        bot.send_message(user_id, msg)
    elif step == "get_batch_numbers":
        print("get batch numbers")
        user_data[user_id]["call_flow_bulk"] = pathway_id
        msg = f"{ENTER_PHONE_NUMBER_PROMPT[lg]} {OR[lg]} " f"{UPLOAD_TXT[lg]}"
        bot.send_message(user_id, msg)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "add_edges"
)
def handle_add_edges(message):
    chat_id = message.chat.id
    lg = get_user_language(chat_id)
    pathway = Pathways.objects.get(pathway_name=user_data[chat_id]["pathway_name"])
    pathway_id = pathway.pathway_id
    response, status = handle_view_single_flow(pathway_id)

    if status != 200:
        bot.send_message(
            chat_id,
            f"{PROCESSING_ERROR[lg]} {response}",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    user_data[chat_id]["data"] = response
    edges = response.get("edges", [])
    nodes = response.get("nodes", [])
    user_data[chat_id]["node_info"] = nodes
    user_data[chat_id]["edge_info"] = edges
    start_node = next(
        (node for node in nodes if node["data"].get("isStart") == True), None
    )

    if not edges:
        if start_node:
            bot.send_message(chat_id, EDGES_LIST_EMPTY[lg])
            markup = types.InlineKeyboardMarkup()
            for node in nodes:
                if node["id"] != start_node["id"]:
                    markup.add(
                        types.InlineKeyboardButton(
                            f"{node['data']['name']}",
                            callback_data=f"target_node_{node['id']}",
                        )
                    )
            user_data[chat_id]["source_node_id"] = f"{start_node['id']}"
            bot.send_message(
                chat_id,
                f"{START_NODE_ID[lg]} {start_node['id']}\n"
                f"{START_NODE_NAME[lg]} {start_node['data']['name']}\n"
                f"{CONNECT_NODE[lg]}",
                reply_markup=markup,
            )
        else:
            bot.send_message(chat_id, NO_START_NODE_FOUND[lg])
    else:
        markup = types.InlineKeyboardMarkup()
        for node in nodes:
            markup.add(
                types.InlineKeyboardButton(
                    f"{node['data']['name']} ({node['id']})",
                    callback_data=f"source_node_{node['id']}",
                )
            )
        bot.send_message(chat_id, SELECT_SOURCE_NODE[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("source_node_"))
def handle_source_node(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    nodes = user_data[call.message.chat.id]["node_info"]
    source_node_id = call.data.split("_")[2]
    user_data[call.message.chat.id]["source_node_id"] = source_node_id
    markup = types.InlineKeyboardMarkup()
    for node in nodes:
        if node["id"] != source_node_id:
            markup.add(
                types.InlineKeyboardButton(
                    f"{node['data']['name']} ({node['id']})",
                    callback_data=f"target_node_{node['id']}",
                )
            )
    bot.send_message(user_id, SELECT_TARGET_NODE[lg], reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("target_node_"))
def handle_target_node(call):
    target_node_id = call.data.split("_")[2]
    chat_id = call.message.chat.id
    lg = get_user_language(chat_id)
    source_node_id = user_data[call.message.chat.id]["source_node_id"]
    user_data[call.message.chat.id]["step"] = "add_label"
    user_data[call.message.chat.id]["src"] = source_node_id
    user_data[call.message.chat.id]["target"] = target_node_id
    bot.send_message(chat_id, ENTER_LABEL_PROMPT[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: "step" in user_data.get(message.chat.id, {})
    and user_data[message.chat.id]["step"] == "add_label"
)
def add_label(message):
    chat_id = message.chat.id
    lg = get_user_language(chat_id)
    label = message.text
    nodes = user_data[chat_id]["node_info"]
    edges = user_data[chat_id]["edge_info"]
    source_node_id = user_data[chat_id]["src"]
    data = user_data[chat_id]["data"]
    pathway_id = user_data[chat_id]["select_pathway"]
    target_node_id = user_data[chat_id]["target"]

    new_edge = {
        "id": f"reactflow__edge-{generate_random_id()}",
        "label": f"{label}",
        "source": f"{source_node_id}",
        "target": f"{target_node_id}",
    }

    edges.append(new_edge)
    updated_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "nodes": nodes,
        "edges": edges,
    }
    response = handle_add_node(pathway_id, updated_data)
    if response.status_code == 200:
        bot.send_message(
            chat_id,
            f"{EDGE_ADDED[lg]}\n"
            f"{SOURCE_NODE[lg]}{source_node_id}\n"
            f"{TARGET_NODE[lg]}{target_node_id}",
            reply_markup=edges_complete_menu(),
        )
        pathway = Pathways.objects.get(pathway_id=pathway_id)
        pathway.pathway_name = data.get("name")
        pathway.pathway_description = data.get("description")
        pathway.pathway_payload = response.text
        pathway.save()

        if message.text not in edges_complete:
            user_data[chat_id]["step"] = "error_edges_complete"
    else:
        bot.send_message(chat_id, f"{PROCESSING_ERROR[lg]} {response}")


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "error_edges_complete"
)
def error_edges_complete(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, MENU_SELECT[lg], reply_markup=edges_complete_menu())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "add_node"
)
def handle_add_node_t(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    node_name = message.text
    pathway_id = user_data[user_id]["select_pathway"]
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get("pathway_data", {})
        nodes = pathway_data.get("nodes", [])
        if any(node["data"]["name"].lower() == node_name.lower() for node in nodes):
            bot.send_message(user_id, f"{NODE_NAME_ALREADY_TAKEN[lg]}")
            return

    user_data[user_id]["add_node"] = node_name
    user_data[user_id]["step"] = "add_node_id"
    bot.send_message(user_id, ASSIGN_NODE_NUMBER[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "add_node_id"
)
def handle_add_node_id(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    pathway_id = user_data[user_id]["select_pathway"]
    existing_nodes = handle_view_single_flow(pathway_id)[0]["nodes"]
    node_ids = [node["id"] for node in existing_nodes]

    if text in node_ids:
        bot.send_message(user_id, NODE_NUMBER_ALREADY_ASSIGNED[lg])
        return

    user_data[user_id]["add_node_id"] = int(text)
    node = user_data[user_id]["node"]

    if node == "Play Message ▶️":
        user_data[user_id]["message_type"] = "Play Message"

        text_to_speech(message)

    elif node == "End Call 🛑":
        user_data[user_id]["message_type"] = "End Call"
        text_to_speech(message)

    elif node == "Get DTMF Input 📞":
        user_data[user_id]["step"] = "get_dtmf_input"
        user_data[user_id]["message_type"] = "DTMF Input"
        bot.send_message(user_id, DTMF_PROMPT[lg], reply_markup=get_force_reply())

    elif node == "Call Transfer 🔄":
        user_data[user_id]["step"] = "get_dtmf_input"
        user_data[user_id]["message_type"] = "Transfer Call"
        bot.send_message(
            user_id,
            ENTER_PHONE_NUMBER_FOR_CALL_TRANSFER[lg],
            reply_markup=get_force_reply(),
        )

    elif node == "Menu 📋":
        user_data[user_id]["step"] = "get_menu"
        bot.send_message(
            user_id, PROMPT_MESSAGE_FOR_MENU[lg], reply_markup=get_force_reply()
        )

    elif node == "Feedback Node":
        user_data[user_id]["message_type"] = "Feedback Node"
        text_to_speech(message)

    elif node == "Question":
        user_data[user_id]["message_type"] = "Question"
        text_to_speech(message)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "get_menu"
)
def get_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    user_data[user_id]["menu_message"] = text
    user_data[user_id]["step"] = "get_action_list"
    bot.send_message(
        user_id, ASSIGN_NUMBERS_FOR_MENU[lg], reply_markup=get_force_reply()
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_action_list"
)
def get_action_list(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    prompt = user_data[user_id]["menu_message"]
    menu = text
    pathway_id = user_data[user_id]["select_pathway"]
    node_name = user_data[user_id]["add_node"]
    node_id = user_data[user_id]["add_node_id"]
    response = handle_menu_node(pathway_id, node_id, prompt, node_name, menu)
    if response.status_code == 200:
        bot.send_message(
            user_id,
            f"'{node_name}' {NODE_ADDED[lg]} ✅",
            reply_markup=get_node_complete_menu(),
        )
        if message.text not in node_complete:
            user_data[user_id]["step"] = "error_nodes_complete"
    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR} {response}")


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "error_nodes_complete"
)
def error_nodes_complete(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECT_FROM_MENU[lg], reply_markup=get_node_complete_menu()
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "text-to-speech"
)
def text_to_speech(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    bot.send_message(
        user_id,
        USE_TEXT_TO_SPEECH_PROMPT[lg],
        reply_markup=get_play_message_input_type(),
    )
    if message.text not in message_input_type:
        user_data[user_id]["step"] = "error_message_input_type"


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "error_message_input_type"
)
def error_message_input_type(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if message.text in message_input_type:
        user_data[user_id]["step"] = "get_node_type"
        return

    bot.send_message(
        user_id, SELECTION_PROMPT[lg], reply_markup=get_play_message_input_type()
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_dtmf_input"
)
def handle_get_dtmf_input(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    pathway_id = user_data[user_id]["select_pathway"]
    node_name = user_data[user_id]["add_node"]
    prompt = text
    node_id = user_data[user_id]["add_node_id"]
    message_type = user_data[user_id]["message_type"]

    if message_type == "Transfer Call":
        if not validate_mobile(text):
            bot.send_message(user_id, INVALID_NUMBER_PROMPT[lg])
            return

    response = handle_dtmf_input_node(
        pathway_id, node_id, prompt, node_name, message_type
    )

    if response.status_code == 200:
        bot.send_message(
            user_id,
            f"'{node_name}'{NODE_ADDED[lg]}! ✅",
            reply_markup=get_node_complete_menu(),
        )
        if message.text not in node_complete:
            user_data[user_id]["step"] = "error_nodes_complete"
    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {response}")


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_node_type"
)
def handle_get_node_type(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    user_data[user_id]["get_node_type"] = text
    node_type = user_data[user_id]["get_node_type"]
    message_type = user_data[user_id]["message_type"]
    if node_type == "Text-to-Speech 🗣️":
        user_data[user_id]["step"] = "play_message"
        bot.send_message(
            user_id,
            f"{ENTER_MESSAGE_PROMPT[lg]} {message_type}: ",
            reply_markup=get_force_reply(),
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "play_message"
)
def handle_play_message(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    if user_data[user_id]["message_type"] == "Feedback Node":
        pathway_id = user_data[user_id]["select_pathway"]

        feedback_log, created = FeedbackLogs.objects.get_or_create(
            pathway_id=pathway_id, defaults={"feedback_questions": []}
        )
        feedback_log.feedback_questions.append(text)
        feedback_log.save()

    user_data[user_id]["play_message"] = text
    user_data[user_id]["step"] = "select_voice_type"
    bot.send_message(
        user_id, SELECT_VOICE_TYPE_PROMPT[lg], reply_markup=get_voice_type_menu()
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "select_voice_type"
)
def handle_select_voice_type(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    user_input = text
    pathway_id = user_data[user_id]["select_pathway"]
    node_name = user_data[user_id]["add_node"]
    node_text = user_data[user_id]["play_message"]
    node_id = user_data[user_id]["add_node_id"]
    if text == "Default John":
        text = "f93094fc-72ac-4fcf-9cf0-83a7fff43e88"
    voice_type = next(
        (voice for voice in voice_data["voices"] if voice["name"] == text), None
    )
    language = user_data[user_id]["select_language"]
    message_type = user_data[user_id]["message_type"]
    if message_type == "Question":
        response = question_type(
            pathway_id, node_name, node_text, node_id, voice_type, language
        )
    else:
        response = play_message(
            pathway_id,
            node_name,
            node_text,
            node_id,
            voice_type,
            language,
            message_type,
        )

    if response.status_code == 200:
        bot.send_message(
            user_id,
            f"'{node_name}' {NODE_ADDED[lg]} ✅",
            reply_markup=get_node_complete_menu(),
        )
        if message.text not in node_complete:
            user_data[user_id]["step"] = "error_nodes_complete"

    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {response}")


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "call_failed"
)
def handle_call_failure(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    bot.send_message(
        user_id, CALL_FAILURE_PROMPT[lg], reply_markup=get_call_failed_menu()
    )
    if message.text not in call_failed_menu:
        user_data[user_id]["step"] = "show_error_call_failed"


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "show_error_call_failed"
)
def handle_show_error_call_failed(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, SELECT_FROM_MENU[lg], reply_markup=get_call_failed_menu())


@bot.message_handler(commands=["transfer"])
def transfer_to_agent(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    phone_numbers = TransferCallNumbers.objects.filter(user_id=user_id).values_list(
        "phone_number", flat=True
    )
    if phone_numbers:
        bot.send_message(
            user_id,
            PREVIOUSLY_ENTERED_NUMBERS[lg],
            reply_markup=get_reply_keyboard(["Yes", "No"]),
        )
        user_data[user_id] = {
            "step": "use_previous_number",
            "phone_numbers": list(phone_numbers),
        }
    else:
        bot.send_message(
            user_id, ENTER_PHONE_NUMBER_TO_TRANSFER[lg], reply_markup=get_force_reply()
        )
        user_data[user_id] = {"step": "enter_new_number"}


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "use_previous_number"
)
def handle_use_previous_number(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    if text == "Yes":
        phone_numbers = user_data[user_id]["phone_numbers"]
        bot.send_message(
            user_id,
            SELECT_PHONE_NUMBER[lg],
            reply_markup=get_inline_keyboard(phone_numbers),
        )
        user_data[user_id]["step"] = "select_phone_number"
    elif text == "No":
        bot.send_message(
            user_id, ENTER_PHONE_NUMBER_TO_TRANSFER[lg], reply_markup=get_force_reply()
        )
        user_data[user_id]["step"] = "enter_new_number"
    else:
        bot.send_message(
            user_id,
            YES_OR_NO_PROMPT[lg],
            reply_markup=get_reply_keyboard(["Yes", "No"]),
        )


@bot.callback_query_handler(
    func=lambda call: user_data.get(call.message.chat.id, {}).get("step")
    == "select_phone_number"
)
def handle_select_phone_number(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    phone_number = call.data
    user_data[user_id]["selected_phone_number"] = phone_number
    bot.send_message(user_id, SETTINGS_SAVED[lg])
    bot.send_message(
        user_id,
        ADD_NODE_OR_DONE_PROMPT[lg],
        reply_markup=get_reply_keyboard(["Add Another Node", "Done"]),
    )
    user_data[user_id]["step"] = "add_or_done"


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "enter_new_number"
)
def handle_enter_new_number(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    phone_number = message.text

    if validate_mobile(phone_number):
        TransferCallNumbers.objects.create(user_id=user_id, phone_number=phone_number)
        user_data[user_id]["selected_phone_number"] = phone_number
        bot.send_message(user_id, SETTINGS_SAVED[lg])
        bot.send_message(
            user_id,
            ADD_NODE_OR_DONE_PROMPT[lg],
            reply_markup=get_reply_keyboard(["Add Another Node", "Done"]),
        )
        user_data[user_id]["step"] = "add_or_done"
    else:
        bot.send_message(
            user_id, INVALID_PHONE_NUMBER[lg], reply_markup=get_force_reply()
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "add_or_done"
)
def handle_add_or_done(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    if text == "Add Another Node":
        user_data[user_id]["step"] = "add_another_node"
        keyboard = check_user_has_active_free_plan(user_id)
        bot.send_message(user_id, SELECT_NODE_TYPE[lg], reply_markup=keyboard)

    elif text == "Done":
        bot.send_message(
            user_id, FINISHED_ADDING_NODES[lg], reply_markup=ivr_flow_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            ADD_ANOTHER_OR_DONE_PROMPT[lg],
            reply_markup=get_reply_keyboard(["Add Another Node", "Done"]),
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "add_another_node"
)
def handle_add_another_node(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    user_data[user_id]["node"] = text
    user_data[user_id]["step"] = "select_pathway"
    view_flows(message)
    bot.send_message(user_id, ENTER_FLOW_NAME[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "initiate_call"
)
def handle_single_ivr_call_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    user_data[user_id]["initiate_call"] = text
    pathway_id = user_data[user_id]["call_flow"]
    phone_number = text
    if validate_mobile(phone_number):

        response, status = send_call_through_pathway(pathway_id, phone_number, user_id)
        if status == 200:
            bot.send_message(
                user_id,
                CALL_QUEUED_SUCCESSFULLY[lg],
                reply_markup=get_main_menu_keyboard(),
            )
            return
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {response}")
    else:
        bot.send_message(
            user_id, INVALID_PHONE_NUMBER[lg], reply_markup=get_force_reply()
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("language:"))
def handle_language_selection(call):
    user_id = call.from_user.id

    selected_language = call.data.split(":")[1]
    print("language : ", {selected_language})
    user_data[user_id] = {"language": selected_language, "step": "get_user_information"}
    user = TelegramUser.objects.get(user_id=user_id)
    user.language = selected_language
    user.save()
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["set_language"] = selected_language
    token = user.token
    signup(call.message)


def handle_terms_and_conditions(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    markup = InlineKeyboardMarkup()
    # url = f"{webhook_url}/terms-and-conditions/"
    url = "https://www.termsfeed.com/blog/sample-terms-and-conditions-template/"
    web_app_info = types.WebAppInfo(url)
    view_terms_button = types.InlineKeyboardButton(
        "📜 View Terms and Conditions", web_app=web_app_info
    )
    accept_button = InlineKeyboardButton("✅ Accept", callback_data="accept_terms")
    decline_terms = InlineKeyboardButton("❌ Decline", callback_data="decline_terms")
    markup.add(view_terms_button)
    markup.add(accept_button)
    markup.add(decline_terms)
    bot.send_message(user_id, REVIEW_TERMS_AND_CONDITIONS[lg], reply_markup=markup)
    user_data[user_id]["step"] = "check_terms_and_conditions"


def view_terms_menu(call):
    handle_terms_and_conditions(call.message)


# Handle Terms Acceptance
@bot.callback_query_handler(
    func=lambda call: call.data in ["accept_terms", "decline_terms"]
)
def handle_terms_response(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if call.data == "accept_terms":
        bot.send_message(
            user_id,
            f"✅ {SUCCESSFULLY_ACCEPTED_TERMS_AND_CONDITIONS[lg]}"
            f"🎉\n{BEGIN_USING_SPEECHCAD[lg]} 🎯",
        )
        bot.send_message(user_id, TERMS_AND_CONDITIONS_TOOLTIP[lg])
        handle_activate_subscription(call)

    elif call.data == "decline_terms":
        markup = types.InlineKeyboardMarkup()
        view_terms_button = types.InlineKeyboardButton(
            "🔄 View Terms Again", callback_data="view_terms_new"
        )
        exit_button = types.InlineKeyboardButton(
            "❌ Exit Setup", callback_data="exit_setup"
        )

        markup.add(view_terms_button, exit_button)
        msg = f"⚠️ {ACCEPT_TERMS_AND_CONDITIONS}"
        bot.send_message(user_id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "view_terms_new")
def handle_view_terms_again(call):
    view_terms_menu(call)


@bot.callback_query_handler(func=lambda call: call.data == "exit_setup")
def handle_exit_setup(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    markup = InlineKeyboardMarkup()
    review_terms = InlineKeyboardButton(
        "📜 View Terms and Conditions", callback_data="view_terms_new"
    )
    markup.add(review_terms)
    bot.send_message(user_id, EXIT_SETUP_PROMPT[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "view_terms")
def handle_view_terms(call):
    user_id = call.from_user.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, f"{VIEW_TERMS_AND_CONDITIONS[lg]} {TERMS_AND_CONDITIONS_URL}"
    )
    handle_activate_subscription(call)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_language")
def handle_back_to_language(call):
    signup(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "Acknowledge and Proceed ✅")
def handle_acknowledge_and_proceed(call):
    user_id = call.from_user.id
    user = TelegramUser.objects.get(user_id=user_id)
    user.save()


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, MAIN_MENU_PROMPT[lg], reply_markup=get_main_menu_keyboard()
    )


def start_bot():
    """
    Start the Telegram bot and initiate infinity polling.
    """
    bot.infinity_polling()
