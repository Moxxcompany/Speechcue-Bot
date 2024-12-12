#-------------- Decorator Functions ---------------#
from django.utils import timezone

from bot.keyboard_menus import get_main_menu
from bot.utils import get_user_language
from payment.models import UserSubscription
from user.models import TelegramUser
from functools import wraps
from translations.translations import *
from bot.bot_config import *
def check_subscription_status(func):
    @wraps(func)
    def wrapper(call, *args, **kwargs):
        user_id = call.message.chat.id
        lg = get_user_language(user_id)

        if check_expiry_date(user_id):
            return func(call, *args, **kwargs)
        else:
            change_subscription_status(user_id)
            bot.send_message(user_id, CHECK_SUBSCRIPTION[lg], reply_markup=get_main_menu())
            return None
    return wrapper

def change_subscription_status(user_id):
    try:
        subscription = UserSubscription.objects.get(user_id__user_id=user_id)
        if subscription.subscription_status != 'inactive':
            subscription.subscription_status = 'inactive'
            subscription.save()
    except UserSubscription.DoesNotExist:
        pass
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        if user.subscription_status != 'inactive':
            user.subscription_status = 'inactive'
            user.save()
    except TelegramUser.DoesNotExist:
        pass


def check_validity(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.chat.id
        lg = get_user_language(user_id)
        if check_expiry_date(user_id):
            return func(message, *args, **kwargs)
        else:
            change_subscription_status(user_id)
            bot.send_message(user_id, CHECK_SUBSCRIPTION[lg], reply_markup=get_main_menu())
            return None

    return wrapper

def check_expiry_date(user_id):
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        user_subscription = UserSubscription.objects.get(user_id=user)
    except TelegramUser.DoesNotExist:
        return False
    except UserSubscription.DoesNotExist:
        return False

    current_date = timezone.now().date()
    print(current_date, " ", user_subscription.date_of_expiry)
    return user_subscription.date_of_expiry and current_date < user_subscription.date_of_expiry
