# :: MENUS ------------------------------------#

from django.core.exceptions import ObjectDoesNotExist
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply,
)

from bot.utils import get_user_language, categorize_voices_by_description
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
    ADD_EDGE,
    FEMALE,
    MALE,
    DTMF_INBOX,
    CALL_STATUS,
    AI_ASSISTED_FLOW,
    CUSTOM_MADE_TASKS,
    CREATE_TASK,
    AI_MADE_TASKS,
    ADVANCED_USER_FLOW_KEYBOARD,
    AI_ASSISTED_FLOW_KEYBOARD,
    CREATE_IVR_FLOW_AI,
    VIEW_FLOWS_AI,
    DELETE_FLOW_AI,
    ADVANCED_USER_FLOW,
    CAMPAIGN_MANAGEMENT,
    SCHEDULED_CAMPAIGNS,
    ACTIVE_CAMPAIGNS,
    RETURN_HOME,
    CAMPAIGN_CALLS,
    RECENT_CALLS,
    # New UI/UX translations
    PHONE_NUMBERS_MENU,
    INBOX_MENU,
    WALLET_AND_BILLING,
    MAKE_CALL_MENU,
    IVR_FLOWS_MENU,
    CAMPAIGNS_MENU,
    MAIN_MENU_BTN,
)


def filter_voices_by_gender(voice_data):
    # voice_data is now a list directly from Retell (not {"voices": [...]})
    voices = voice_data if isinstance(voice_data, list) else voice_data.get("voices", [])
    male_voices = categorize_voices_by_description(voices, "Male")
    female_voices = categorize_voices_by_description(voices, "Female")

    return male_voices, female_voices


voice_data = get_voices()
male_voices, female_voices = filter_voices_by_gender(voice_data)


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


def get_task_type_keyboard(user_id):
    lg = get_user_language(user_id)
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton(AI_MADE_TASKS[lg]))
    markup.add(types.KeyboardButton(CUSTOM_MADE_TASKS[lg]))
    markup.add(types.KeyboardButton(CREATE_TASK[lg]))
    return markup


def get_create_task_keyboard(user_id):
    lg = get_user_language(user_id)
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton(AI_ASSISTED_FLOW[lg]))
    markup.add(types.KeyboardButton(ADVANCED_USER_FLOW[lg]))
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
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        KeyboardButton(f"📞 {PHONE_NUMBERS_MENU[lg]}"),
        KeyboardButton(f"🎙 {IVR_FLOWS_MENU[lg]}"),
    )
    markup.row(
        KeyboardButton(f"☎️ {MAKE_CALL_MENU[lg]}"),
        KeyboardButton(f"📋 {CAMPAIGNS_MENU[lg]}"),
    )
    markup.row(
        KeyboardButton(f"📬 {INBOX_MENU[lg]}"),
        KeyboardButton(f"💰 {WALLET_AND_BILLING[lg]}"),
    )
    markup.row(
        KeyboardButton(ACCOUNT[lg]),
        KeyboardButton(HELP[lg]),
    )
    return markup


def get_force_reply():
    return ForceReply(selective=False)


def ivr_flow_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [AI_ASSISTED_FLOW_KEYBOARD[lg], ADVANCED_USER_FLOW_KEYBOARD[lg]]
    return get_reply_keyboard(options)


def ai_assisted_user_flow_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [
        CREATE_IVR_FLOW_AI[lg],
        VIEW_FLOWS_AI[lg],
        DELETE_FLOW_AI[lg],
        BACK_BUTTON[lg],
    ]
    return get_reply_keyboard(options)


def advanced_user_flow_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [CREATE_IVR_FLOW[lg], VIEW_FLOWS[lg], DELETE_FLOW[lg], BACK_BUTTON[lg]]
    return get_reply_keyboard(options)


def ivr_call_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [SINGLE_IVR[lg], BULK_CALL[lg], CALL_STATUS[lg], BACK_BUTTON[lg]]
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


def get_voice_type_menu(gender):

    if gender in FEMALE.values():
        options = [voice["name"] for voice in female_voices][:20]
    elif gender in MALE.values():
        options = [voice["name"] for voice in male_voices][:20]
    else:
        options = ["Invalid gender specified"]

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
    options = [ADD_NODE[lg], DELETE_NODE[lg], ADD_EDGE[lg], BACK[lg]]
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


# -------------Campaign Managemenet---------------


def get_campaign_management_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [SCHEDULED_CAMPAIGNS[lg], ACTIVE_CAMPAIGNS[lg], RETURN_HOME[lg]]
    return get_reply_keyboard(options)


# -------------Inbox---------------------


def inbox_keyboard(user_id):
    lg = get_user_language(user_id)
    options = [SINGLE_IVR[lg], CAMPAIGN_CALLS[lg], RECENT_CALLS[lg]]
    return get_reply_keyboard(options)


# =============================================================================
# New Hub Keyboards
# =============================================================================


def get_phone_numbers_hub_keyboard(user_id):
    """Phone Numbers hub — inline keyboard."""
    from bot.models import UserPhoneNumber, SMSInbox
    lg = get_user_language(user_id)

    num_count = UserPhoneNumber.objects.filter(user_id=user_id, is_active=True).count()
    sms_unread = SMSInbox.objects.filter(user_id=user_id, is_read=False).count()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🛒 Buy New Number", callback_data="buy_number"
    ))
    my_nums_label = f"📋 My Numbers ({num_count})" if num_count else "📋 My Numbers"
    markup.add(types.InlineKeyboardButton(
        my_nums_label, callback_data="my_numbers"
    ))
    sms_label = f"📨 SMS Inbox ({sms_unread} new)" if sms_unread else "📨 SMS Inbox"
    markup.add(types.InlineKeyboardButton(
        sms_label, callback_data="sms_inbox"
    ))
    markup.add(types.InlineKeyboardButton(
        f"🔙 {MAIN_MENU_BTN[lg]}", callback_data="back_to_welcome_message"
    ))
    return markup


def get_inbox_hub_keyboard(user_id):
    """Inbox hub — inline keyboard."""
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "📞 Call Recordings", callback_data="call_recordings"
    ))
    markup.add(types.InlineKeyboardButton(
        "🔢 DTMF Responses", callback_data="dtmf_responses_hub"
    ))
    markup.add(types.InlineKeyboardButton(
        "📨 SMS Messages", callback_data="sms_inbox"
    ))
    markup.add(types.InlineKeyboardButton(
        "📊 Call History", callback_data="call_history"
    ))
    markup.add(types.InlineKeyboardButton(
        f"🔙 {MAIN_MENU_BTN[lg]}", callback_data="back_to_welcome_message"
    ))
    return markup


def get_wallet_billing_keyboard(user_id):
    """Wallet & Billing hub — inline keyboard."""
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "💳 Top Up Wallet", callback_data="top_up_wallet"
    ))
    markup.add(types.InlineKeyboardButton(
        "📜 Transaction History", callback_data="transaction_history"
    ))
    markup.add(types.InlineKeyboardButton(
        f"📋 {VIEW_SUBSCRIPTION[lg]}", callback_data="view_subscription"
    ))
    markup.add(types.InlineKeyboardButton(
        f"⬆️ {UPGRADE_SUBSCRIPTION[lg]}", callback_data="update_subscription"
    ))
    markup.add(types.InlineKeyboardButton(
        f"🔙 {MAIN_MENU_BTN[lg]}", callback_data="back_to_welcome_message"
    ))
    return markup


def get_onboarding_keyboard(user_id):
    """Post-onboarding keyboard with Free plan and Premium options."""
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🎉 Activate Free Plan", callback_data="activate_free_plan"
    ))
    markup.add(types.InlineKeyboardButton(
        "💎 View Premium Plans", callback_data="activate_subscription"
    ))
    markup.add(types.InlineKeyboardButton(
        "📖 How It Works", callback_data="how_it_works"
    ))
    return markup

