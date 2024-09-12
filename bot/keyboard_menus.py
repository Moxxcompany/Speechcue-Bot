# :: MENUS ------------------------------------#
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, \
    ReplyKeyboardRemove

from bot.views import get_voices

voice_data = get_voices()


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
    options = ["Create IVR Flow ➕", "View Flows 📂", "Delete Flow ❌", "Help ℹ️"]
    return get_reply_keyboard(options)

def get_gender_menu():
    options = ["Male", "Female"]
    return get_reply_keyboard(options)


languages = ["English", "Indian Language", "Chinese", "French"]


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

