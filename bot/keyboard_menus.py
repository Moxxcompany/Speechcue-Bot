# :: MENUS ------------------------------------#


from django.core.exceptions import ObjectDoesNotExist
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

from bot.telegrambot import DEFAULT_LANGUAGE
from bot.views import get_voices
from telebot import types

from payment.models import UserSubscription

voice_data = get_voices()


def check_user_has_active_free_plan(user_id):
    try:
        active_subscription = UserSubscription.objects.get(
            user_id=user_id,
            subscription_status='active'
        )

        free_plan = active_subscription.plan_id.plan_price == 0

        if free_plan:
            return get_node_menu_free()
        else:
            return get_node_menu()

    except ObjectDoesNotExist:
        return get_node_menu()

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

def get_available_commands():
    options = ["Create IVR Flow ➕", "View Flows 📂", "Delete Flow ❌", "Help ℹ️", "Back to Main Menu ↩️"]
    return get_reply_keyboard(options)

def get_gender_menu():
    options = ["Male", "Female"]
    return get_reply_keyboard(options)


languages_flag = [
    ("English", "🇬🇧"),
    ("Hindi", "🇮🇳"),
    ("Chinese", "🇨🇳"),
    ("French", "🇫🇷")
]


def get_language_markup(callback_query_string):
    markup = types.InlineKeyboardMarkup()
    for language, flag in languages_flag:
        language_button = types.InlineKeyboardButton(
            text=f"{language} {flag} ",
            callback_data=f"{callback_query_string}:{language}"
        )
        markup.add(language_button)
    return markup
def get_language_flag_menu():
    options = [lang for lang, _ in languages_flag]
    return get_reply_keyboard(options)



def get_voice_type_menu():
    options = [voice['name'] for voice in voice_data['voices']]
    return get_reply_keyboard(options)


message_input_type = ["Text-to-Speech 🗣️", "Back ↩️"]


def get_play_message_input_type():
    options = message_input_type
    return get_reply_keyboard(options)

def get_subscription_activation_markup():
    markup = InlineKeyboardMarkup()
    activate_subscription_button = InlineKeyboardButton("Activate Subscription ⬆️,",
                                                              callback_data="activate_subscription")
    back_button = InlineKeyboardButton("Back ↩️", callback_data="back_to_welcome_message")
    markup.add(activate_subscription_button)
    markup.add(back_button)
    return markup
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
def get_node_menu_free():
    options =[
        "Play Message ▶️",
        "Get DTMF Input 📞",
        "End Call 🛑",
        "Menu 📋",
        "Feedback Node",
        "Question",
        "Back to Main Menu ↩️"
    ]
    return get_reply_keyboard(options)

def get_billing_and_subscription_keyboard():

    markup = types.InlineKeyboardMarkup()
    view_subscription_btn = types.InlineKeyboardButton('View Subscription 📅', callback_data='view_subscription')
    update_subscription_btn = types.InlineKeyboardButton('Upgrade Subscription ⬆️', callback_data='update_subscription')
    wallet_btn = types.InlineKeyboardButton('Wallet 💰', callback_data='check_wallet')
    help_btn = types.InlineKeyboardButton("Help ℹ️", callback_data='help')
    back_btn = types.InlineKeyboardButton('Back ↩️', callback_data='back_to_welcome_message')
    markup.add(view_subscription_btn)
    markup.add(update_subscription_btn)
    markup.add(wallet_btn)
    markup.add(back_btn)
    return markup

def get_currency_keyboard():
    markup = types.InlineKeyboardMarkup()
    payment_methods = ['Bitcoin (BTC) ₿', 'Ethereum (ETH) Ξ', 'TRC-20 USDT 💵', 'ERC-20 USDT 💵',
                       'Litecoin (LTC) Ł', 'Back ↩️']
    for method in payment_methods:
        payment_button = types.InlineKeyboardButton(method, callback_data=f"pay_{method.lower().replace(' ', '_')}")
        markup.add(payment_button)

    return markup

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

