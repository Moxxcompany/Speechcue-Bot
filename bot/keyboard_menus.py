# :: MENUS ------------------------------------#

from django.core.exceptions import ObjectDoesNotExist
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply,
)

from bot.utils import get_user_language
from bot.views import get_voices
from telebot import types
from payment.models import UserSubscription

from translations.translations import (
    JOIN_CHANNEL,
    HELP,
    TEXT_TO_SPEECH,
    BACK_BUTTON,
    ACTIVATE_SUBSCRIPTION_BUTTON,
    PLAY_MESSAGE,
    GET_DTMF_INPUT,
    END_CALL,
    CALL_TRANSFER_NODE,
    MENU,
    FEEDBACK_NODE,
    QUESTION,
    BACK_TO_MAIN_MENU,
    WALLET_BUTTON,
    UPGRADE_SUBSCRIPTION,
    CONFIRM_DELETE,
    TOP_UP,
    BILLING_AND_SUBSCRIPTION,
    IVR_CALL,
    IVR_FLOW,
    ACCOUNT,
    CREATE_IVR_FLOW,
    VIEW_FLOWS,
    SINGLE_IVR,
    PROFILE,
    USER_FEEDBACK,
    DELETE_FLOW,
    SETTINGS,
    VIEW_SUBSCRIPTION,
    CHANGE_LANGUAGE_BUTTON,
    VIEW_TERMS_AND_CONDITIONS,
    ADD_ANOTHER_PHONE_NUMBER,
    DONE_ADDING_PHONE_NUMBERS,
    ADD_NODE,
    DELETE_NODE,
    BACK,
    RETRY_NODE,
    SKIP_NODE,
    TRANSFER_TO_LIVE_AGENT,
    CONTINUE_ADDING_EDGES,
    DONE_ADDING_EDGES,
    CONTINUE_TO_NEXT_NODE,
    DONE_ADDING_NODES,
    CALL_TRANSFER,
    ADD_ANOTHER_NODE,
    DONE,
    BULK_CALL,
    YES,
    NO,
)

voice_data = get_voices()


def check_user_has_active_free_plan(user_id):

    try:
        active_subscription = UserSubscription.objects.get(
            user_id=user_id, subscription_status="active"
        )
        call_transfer = active_subscription.call_transfer
        if call_transfer:
            return get_node_menu(user_id)
        else:
            return get_node_menu_free(user_id)
    except ObjectDoesNotExist:
        return get_node_menu(user_id)


def get_reply_keyboard(options):
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for option in options:
        markup.add(KeyboardButton(option))
    return markup


def get_delete_confirmation_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [CONFIRM_DELETE[lg], BACK_BUTTON[lg]]
    return get_reply_keyboard(options)


def get_inline_keyboard(options):
    markup = InlineKeyboardMarkup()
    for option in options:
        markup.add(InlineKeyboardButton(option, callback_data=option))
    return markup


def get_main_menu_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [
        TOP_UP[lg],
        BILLING_AND_SUBSCRIPTION[lg],
        IVR_FLOW[lg],
        IVR_CALL[lg],
        ACCOUNT[lg],
    ]
    return get_reply_keyboard(options)


def get_force_reply():
    return ForceReply(selective=False)


def ivr_flow_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [CREATE_IVR_FLOW[lg], VIEW_FLOWS[lg], DELETE_FLOW[lg], BACK_BUTTON[lg]]
    return get_reply_keyboard(options)


def ivr_call_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [SINGLE_IVR[lg], BULK_CALL[lg], BACK_BUTTON[lg]]
    return get_reply_keyboard(options)


def account_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [PROFILE[lg], SETTINGS[lg], USER_FEEDBACK[lg], BACK_BUTTON[lg]]
    return get_reply_keyboard(options)


def support_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [JOIN_CHANNEL[lg], HELP[lg]]
    return get_reply_keyboard(options)


def get_main_menu():
    options = [
        "Create IVR Flow ➕",
        "View Flows 📂",
        "Delete Flow ❌",
        "Help ℹ️",
        "Single IVR Call ☎️",
        "Bulk IVR Call 📞📞",
        "Billing and Subscription 📅",
        "Join Channel 🔗",
        "Profile 👤",
        "Settings ⚙",
        "View Feedback",
        "View Variables",
    ]
    return get_reply_keyboard(options)


def get_available_commands():
    options = [
        "Create IVR Flow ➕",
        "View Flows 📂",
        "Delete Flow ❌",
        "Help ℹ️",
        "Back to Main Menu ↩️",
    ]
    return get_reply_keyboard(options)


languages_flag = [
    ("English", "🇬🇧"),
    ("Hindi", "🇮🇳"),
    ("Chinese", "🇨🇳"),
    ("French", "🇫🇷"),
]


def get_language_markup(callback_query_string):
    markup = types.InlineKeyboardMarkup()
    for language, flag in languages_flag:
        language_button = types.InlineKeyboardButton(
            text=f"{language} {flag} ",
            callback_data=f"{callback_query_string}:{language}",
        )
        markup.add(language_button)
    return markup


def get_language_flag_menu():
    options = [lang for lang, _ in languages_flag]
    return get_reply_keyboard(options)


def get_voice_type_menu():
    options = [voice["name"] for voice in voice_data["voices"]][:20]
    return get_reply_keyboard(options)


def get_play_message_input_type(user_id):
    options = get_message_input_type_list(user_id)
    return get_reply_keyboard(options)


def get_message_input_type_list(user_id):
    lg = get_user_language(user_id)
    message_input_type = [TEXT_TO_SPEECH[lg], BACK_BUTTON[lg]]
    return message_input_type


def get_subscription_activation_markup(user_id):
    lg = get_user_language(user_id)
    markup = InlineKeyboardMarkup()
    activate_subscription_button = InlineKeyboardButton(
        ACTIVATE_SUBSCRIPTION_BUTTON[lg], callback_data="activate_subscription"
    )
    back_button = InlineKeyboardButton(
        BACK_BUTTON[lg], callback_data="back_to_welcome_message"
    )
    markup.add(activate_subscription_button)
    markup.add(back_button)
    return markup


# todo : start changes from here for menu translations
def get_node_menu(user_id):
    lg = get_user_language(user_id)
    options = [
        PLAY_MESSAGE[lg],
        GET_DTMF_INPUT[lg],
        END_CALL[lg],
        CALL_TRANSFER[lg],
        MENU[lg],
        FEEDBACK_NODE[lg],
        QUESTION[lg],
        BACK_TO_MAIN_MENU[lg],
    ]
    return get_reply_keyboard(options)


def get_node_menu_free(user_id):
    lg = get_user_language(user_id)
    options = [
        PLAY_MESSAGE[lg],
        GET_DTMF_INPUT[lg],
        END_CALL[lg],
        MENU[lg],
        FEEDBACK_NODE[lg],
        QUESTION[lg],
        BACK_TO_MAIN_MENU[lg],
    ]
    return get_reply_keyboard(options)


def get_billing_and_subscription_keyboard(user_id):
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    view_subscription_btn = types.InlineKeyboardButton(
        VIEW_SUBSCRIPTION[lg], callback_data="view_subscription"
    )
    update_subscription_btn = types.InlineKeyboardButton(
        UPGRADE_SUBSCRIPTION[lg], callback_data="update_subscription"
    )
    wallet_btn = types.InlineKeyboardButton(
        WALLET_BUTTON[lg], callback_data="check_wallet"
    )
    help_btn = types.InlineKeyboardButton(HELP[lg], callback_data="help")
    back_btn = types.InlineKeyboardButton(
        BACK_BUTTON[lg], callback_data="back_to_welcome_message"
    )
    markup.add(view_subscription_btn)
    markup.add(update_subscription_btn)
    markup.add(wallet_btn)
    markup.add(back_btn)
    return markup


def get_currency_keyboard(user_id):
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    payment_methods = [
        "Bitcoin (BTC) ₿",
        "Ethereum (ETH) Ξ",
        "TRC-20 USDT 💵",
        "ERC-20 USDT 💵",
        "Litecoin (LTC) Ł",
        BACK_BUTTON[lg],
    ]
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(
            method, callback_data=f"pay_{method.lower().replace(' ', '_')}"
        )
        markup.add(payment_button)

    return markup


def get_setting_keyboard(user_id):
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    change_language_btn = types.InlineKeyboardButton(
        CHANGE_LANGUAGE_BUTTON[lg], callback_data="change_language"
    )
    back_btn = types.InlineKeyboardButton(BACK_BUTTON[lg], callback_data="back_account")
    markup.add(change_language_btn)
    markup.add(back_btn)
    return markup


def get_terms_and_conditions(user_id):
    lg = get_user_language(user_id)
    options = [VIEW_TERMS_AND_CONDITIONS[lg], BACK_BUTTON[lg]]
    return get_reply_keyboard(options)


def get_yes_no_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [ADD_ANOTHER_PHONE_NUMBER[lg], DONE_ADDING_PHONE_NUMBERS[lg]]
    return get_reply_keyboard(options)


def yes_or_no(user_id):
    lg = get_user_language(user_id)
    options = [YES[lg], NO[lg]]
    return get_reply_keyboard(options)


def get_flow_node_menu(user_id):
    lg = get_user_language(user_id)
    options = [ADD_NODE[lg], DELETE_NODE[lg], BACK[lg]]
    return get_reply_keyboard(options)


def get_call_failed_menu_list(user_id):
    lg = get_user_language(user_id)
    call_failed_menu = [
        RETRY_NODE[lg],
        SKIP_NODE[lg],
        TRANSFER_TO_LIVE_AGENT[lg],
        BACK_BUTTON[lg],
    ]
    return call_failed_menu


def get_call_failed_menu(user_id):
    options = get_call_failed_menu_list(user_id)
    return get_reply_keyboard(options)


def edges_complete_options(user_id):
    lg = get_user_language(user_id)
    edges_complete = [CONTINUE_ADDING_EDGES[lg], DONE_ADDING_EDGES[lg]]
    return edges_complete


def edges_complete_menu(user_id):
    options = edges_complete_options(user_id)
    return get_reply_keyboard(options)


def node_complete_options(user_id):
    lg = get_user_language(user_id)
    node_complete = [
        CONTINUE_TO_NEXT_NODE[lg],
        DONE_ADDING_NODES[lg],
    ]
    return node_complete


def get_node_complete_menu(user_id):
    options = node_complete_options(user_id)
    return get_reply_keyboard(options)


def get_add_another_node_or_done_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [ADD_ANOTHER_NODE[lg], DONE[lg]]
    return get_reply_keyboard(options)
