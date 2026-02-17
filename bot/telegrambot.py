import base64
from io import BytesIO
from PIL import Image
import json
from uuid import UUID
import re
import io
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from phonenumbers import geocoder
from calendar import isleap
from datetime import datetime, timedelta
import phonenumbers
from timezonefinder import TimezoneFinder

import bot.bot_config
from TelegramBot.constants import STATUS_CODE_200, MAX_INFINITY_CONSTANT
from bot.tasks import execute_bulk_ivr, send_reminder, cancel_scheduled_call
from payment.decorator_functions import (
    check_expiry_date,
)
import pytz
from geopy.geocoders import Nominatim


from translations.translations import *  # noqa

from bot.models import (
    Pathways,
    TransferCallNumbers,
    FeedbackLogs,
    CallLogsTable,
    CallDuration,
    AI_Assisted_Tasks,
    CallerIds,
    CampaignLogs,
    ScheduledCalls,
)

from bot.utils import (
    generate_random_id,
    username_formating,
    validate_edges,
    get_currency,
    set_user_subscription,
    set_plan,
    set_details_for_user_table,
    get_plan_price,
    get_user_language,
    reset_user_language,
    get_subscription_day,
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
    handle_transfer_call_node,
    get_call_status,
    send_task_through_call,
    make_wizard_test_call,
)

from bot.call_gate import pre_call_check, pre_call_check_bulk, classify_destination
from bot.retell_service import (
    purchase_phone_number, release_phone_number, update_phone_number_agent,
    get_retell_phone_number_set, sync_caller_ids_with_retell,
    update_agent_inbound_settings,
)
from bot.models import UserPhoneNumber, PendingPhoneNumberPurchase, PendingDTMFApproval, SMSInbox

from payment.models import SubscriptionPlans, DTMF_Inbox
from payment.views import (
    setup_user,
    check_user_balance,
    create_crypto_payment,
    credit_wallet_balance,
    credit_wallet,
    debit_wallet,
    refund_wallet,
)

from user.models import TelegramUser
from bot.keyboard_menus import *  # noqa
from bot.bot_config import *  # noqa

from bot.callback_query_handlers import *  # noqa

from payment.models import WalletTransaction, TransactionType
from translations.translations import (
    WELCOME_BACK, DASHBOARD_SUMMARY, PLAN_LABEL, WALLET_LABEL, NUMBERS_LABEL,
    MINUTES_LEFT_LABEL, PHONE_NUMBERS_MENU, INBOX_MENU, WALLET_AND_BILLING,
    MAKE_CALL_MENU, IVR_FLOWS_MENU, CAMPAIGNS_MENU, PHONE_NUMBERS_HUB,
    INBOX_HUB, NO_CALLS_YET, NO_TRANSACTIONS_YET, NO_RECORDINGS_YET,
    NO_NUMBERS_YET, QUICK_START_TITLE, QUICK_START_STEP_1, QUICK_START_STEP_2,
    QUICK_START_STEP_3, QUICK_START_STEP_4, FREE_PLAN_ACTIVATED,
    HOW_IT_WORKS_TEXT, CALL_HISTORY_MENU, CALL_RECORDINGS_MENU,
    TRANSACTION_HISTORY, VIEW_ALL_CALLS, VIEW_ALL_TRANSACTIONS,
    SMS_INBOX_MENU, MY_NUMBERS, MAIN_MENU_BTN, BACK_BTN,
    WIZARD_OFFER, WIZARD_TRY_CALL, WIZARD_SKIP, WIZARD_ENTER_PHONE,
    WIZARD_CALLING, WIZARD_SUCCESS, WIZARD_FAILED,
    CANCEL_CONFIRM, SCHEDULE_TIMEZONE_HINT,
)

ADMIN_USERNAMES = {"onarrival1"}  # Telegram usernames (without @) that get admin privileges


def _sync_telegram_username(from_user):
    """Capture/update Telegram username and auto-flag admins on every interaction."""
    if not from_user:
        return
    user_id = from_user.id
    tg_username = (from_user.username or "").lower()
    try:
        user = TelegramUser.objects.filter(user_id=user_id).first()
        if user:
            changed = False
            if tg_username and user.telegram_username != tg_username:
                user.telegram_username = tg_username
                changed = True
            if tg_username in ADMIN_USERNAMES and not user.is_admin:
                user.is_admin = True
                changed = True
            if changed:
                user.save(update_fields=["telegram_username", "is_admin"])
    except Exception:
        pass


VALID_NODE_TYPES = [
    "End Call 🛑",
    "Call Transfer 🔄",
    "Collect Keypress 📞",
    "Play Message ▶️",
    "Menu 📋",
    "Feedback Step",
    "Question",
]
available_commands = {
    "/create_flow": "Create a new call script",
    "/view_flows": "View all call scripts",
    "/add_node": "Add a step to a script",
}
webhook_url = os.getenv("webhook_url")


call_data = []
TERMS_AND_CONDITIONS_URL = os.getenv("TERMS_AND_CONDITIONS_URL")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")


# Global exception handler — logs handler crashes instead of silently swallowing them
import logging as _logging
_handler_logger = _logging.getLogger("bot.handlers")


class BotExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exception):
        _handler_logger.error(f"Bot handler exception: {exception}", exc_info=True)
        return True

bot.exception_handler = BotExceptionHandler()



# /cancel handler — clears any active step and returns to main menu
@bot.message_handler(commands=["cancel"])
def handle_cancel_command(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id in user_data:
        user_data[user_id]["step"] = ""
    bot.send_message(user_id, CANCEL_CONFIRM[lg], reply_markup=get_main_menu_keyboard(user_id))


@bot.message_handler(func=lambda message: message.text and message.text.lower() == "cancel"
                      and user_data.get(message.chat.id, {}).get("step", ""))
def handle_cancel_text(message):
    """Handle 'Cancel' button press during any multi-step flow."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id in user_data:
        user_data[user_id]["step"] = ""
    bot.send_message(user_id, CANCEL_CONFIRM[lg], reply_markup=get_main_menu_keyboard(user_id))



# =============================================================================
# New UI/UX Hub Handlers
# =============================================================================

def _match_menu_text(message_text, translations_dict):
    """Match message text against translated menu buttons with emoji prefix."""
    for lg, text in translations_dict.items():
        # Match with various emoji prefixes
        for prefix in ["📞 ", "🎙 ", "☎️ ", "📋 ", "📬 ", "💰 ", "👤 ", "❓ ", ""]:
            if message_text == f"{prefix}{text}":
                return True
    return False


@bot.message_handler(func=lambda message: _match_menu_text(message.text or "", PHONE_NUMBERS_MENU))
def handle_phone_numbers_hub(message):
    """Phone Numbers hub — main menu entry point."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_phone_numbers_hub_keyboard
    bot.send_message(
        user_id,
        f"📞 *{PHONE_NUMBERS_MENU[lg]}*\n\n{PHONE_NUMBERS_HUB[lg]}",
        reply_markup=get_phone_numbers_hub_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: _match_menu_text(message.text or "", INBOX_MENU))
def handle_inbox_hub(message):
    """Inbox hub — consolidates SMS, DTMF, Call History, Recordings."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_inbox_hub_keyboard
    bot.send_message(
        user_id,
        f"📬 *{INBOX_MENU[lg]}*\n\n{INBOX_HUB[lg]}",
        reply_markup=get_inbox_hub_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: _match_menu_text(message.text or "", WALLET_AND_BILLING))
def handle_wallet_billing_hub(message):
    """Wallet & Billing hub — shows balance + options."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_wallet_billing_keyboard
    wallet = check_user_balance(user_id)
    balance = wallet.get("data", {}).get("amount", 0) if wallet.get("data") else 0
    bot.send_message(
        user_id,
        f"💰 *{WALLET_AND_BILLING[lg]}*\n\n💵 Balance: *${balance}*",
        reply_markup=get_wallet_billing_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: _match_menu_text(message.text or "", MAKE_CALL_MENU))
def handle_make_call_menu(message):
    """Make a Call — redirects to the existing IVR call flow."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, f"☎️ {SELECTION_PROMPT[lg]}",
        reply_markup=ivr_call_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: _match_menu_text(message.text or "", IVR_FLOWS_MENU))
def handle_ivr_flows_menu(message):
    """IVR Flows — redirects to the existing IVR flow keyboard."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, f"🎙 {CHOOSE_IVR_FLOW_TYPE[lg]}",
        reply_markup=ivr_flow_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: _match_menu_text(message.text or "", CAMPAIGNS_MENU))
def handle_campaigns_menu(message):
    """Campaigns — redirects to the existing campaign management."""
    user_id = message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_campaign_management_keyboard
    bot.send_message(
        user_id, f"📋 {SELECTION_PROMPT[lg]}",
        reply_markup=get_campaign_management_keyboard(user_id),
    )


# --- Inline callback handlers for new hubs ---

@bot.callback_query_handler(func=lambda call: call.data == "call_history")
def handle_call_history(call):
    """Show recent call history."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    calls = CallLogsTable.objects.filter(user_id=user_id).order_by("-created_at")[:10]

    if not calls.exists():
        bot.send_message(user_id, f"📊 {NO_CALLS_YET[lg]}")
        return

    lines = [f"📊 *{CALL_HISTORY_MENU[lg]}*\n"]
    for i, c in enumerate(calls, 1):
        status_icon = "✅" if c.call_status == "complete" else "⏳" if c.call_status == "pending" else "❌"
        # Get duration if available
        try:
            cd = CallDuration.objects.get(call_id=c.call_id)
            dur = f"{cd.duration_in_seconds / 60:.1f} min" if cd.duration_in_seconds else "N/A"
        except CallDuration.DoesNotExist:
            dur = "N/A"

        date_str = c.created_at.strftime("%b %d, %H:%M") if c.created_at else ""
        lines.append(f"{i}. {status_icon} `{c.call_number}` — {dur} — {date_str}")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"🔙 {BACK_BTN[lg]}", callback_data="inbox_hub_back"
    ))
    bot.send_message(user_id, "\n".join(lines), reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "call_recordings")
def handle_call_recordings(call):
    """Show recent call recordings from Retell."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    # Get recent completed calls that might have recordings
    calls = CallLogsTable.objects.filter(
        user_id=user_id, call_status="complete"
    ).order_by("-created_at")[:10]

    if not calls.exists():
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="inbox_hub_back"))
        bot.send_message(user_id, f"🎙 {NO_RECORDINGS_YET[lg]}", reply_markup=markup)
        return

    lines = [f"🎙 *{CALL_RECORDINGS_MENU[lg]}*\n"]
    markup = types.InlineKeyboardMarkup()

    for i, c in enumerate(calls, 1):
        try:
            cd = CallDuration.objects.get(call_id=c.call_id)
            dur = f"{cd.duration_in_seconds / 60:.1f} min" if cd.duration_in_seconds else "N/A"
        except CallDuration.DoesNotExist:
            dur = "N/A"
        date_str = c.created_at.strftime("%b %d, %H:%M") if c.created_at else ""
        lines.append(f"{i}. `{c.call_number}` — {dur} — {date_str}")
        markup.add(types.InlineKeyboardButton(
            f"🔊 #{i} — {c.call_number}",
            callback_data=f"play_recording_{c.call_id[:40]}"
        ))

    markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="inbox_hub_back"))
    bot.send_message(user_id, "\n".join(lines), reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("play_recording_"))
def handle_play_recording(call):
    """Fetch and send call recording inline in Telegram."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    call_id = call.data.replace("play_recording_", "")

    try:
        from bot.models import CallRecording
        from bot.recording_utils import download_recording as dl_recording

        # Check if we already have a cached recording
        rec = CallRecording.objects.filter(call_id__startswith=call_id).first()
        if rec and rec.downloaded and rec.file_path and os.path.exists(rec.file_path):
            # Send cached audio inline
            call_log = CallLogsTable.objects.filter(call_id__startswith=call_id).first()
            to_num = call_log.call_number if call_log else "Unknown"
            with open(rec.file_path, "rb") as af:
                bot.send_audio(
                    user_id, af,
                    caption=f"🎙 *Recording* — `{to_num}`",
                    parse_mode="Markdown",
                    title=f"Call Recording {to_num}",
                    performer="Speechcue",
                )
            return

        # No cached copy — fetch from Retell
        from retell import Retell
        retell_client = Retell(api_key=os.environ.get("RETELL_API_KEY"))
        # Reconstruct full call_id if truncated
        full_call_log = CallLogsTable.objects.filter(call_id__startswith=call_id).first()
        full_call_id = full_call_log.call_id if full_call_log else call_id
        call_detail = retell_client.call.retrieve(full_call_id)
        recording_url = getattr(call_detail, "recording_url", None)

        if recording_url:
            bot.send_message(user_id, "🎙 Downloading recording...")
            file_path = dl_recording(full_call_id, recording_url)
            if file_path and os.path.exists(file_path):
                to_num = full_call_log.call_number if full_call_log else "Unknown"
                with open(file_path, "rb") as af:
                    bot.send_audio(
                        user_id, af,
                        caption=f"🎙 *Recording* — `{to_num}`",
                        parse_mode="Markdown",
                        title=f"Call Recording {to_num}",
                        performer="Speechcue",
                    )
            else:
                # Fallback to link
                bot.send_message(
                    user_id,
                    f"🎙 *Call Recording*\nCall: `{call_id[:12]}...`\n\n"
                    f"[Listen to Recording]({recording_url})",
                    parse_mode="Markdown",
                )
        else:
            bot.send_message(user_id, "No recording available for this call.")
    except Exception as e:
        bot.send_message(user_id, f"Could not retrieve recording: {str(e)[:100]}")


@bot.callback_query_handler(func=lambda call: call.data == "transaction_history")
def handle_transaction_history(call):
    """Show wallet transaction history."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    txs = WalletTransaction.objects.filter(user__user_id=user_id).order_by("-created_at")[:15]

    if not txs.exists():
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="wallet_hub_back"))
        bot.send_message(user_id, f"📜 {NO_TRANSACTIONS_YET[lg]}", reply_markup=markup)
        return

    lines = [f"📜 *{TRANSACTION_HISTORY[lg]}*\n"]
    type_icons = {
        "SUB": "📋", "OVR": "⚡", "WDR": "📤",
        "DEP": "📥", "TRF": "🔄", "RFD": "💫",
    }
    for tx in txs:
        icon = type_icons.get(tx.transaction_type, "💳")
        sign = "+" if tx.transaction_type in ("DEP", "RFD") else "-"
        date_str = tx.created_at.strftime("%b %d") if tx.created_at else ""
        desc = (tx.description or tx.get_transaction_type_display())[:35]
        lines.append(f"{icon} {sign}${tx.amount} — {desc} — {date_str}")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="wallet_hub_back"))
    bot.send_message(user_id, "\n".join(lines), reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "dtmf_responses_hub")
def handle_dtmf_responses_hub(call):
    """Redirect to existing DTMF inbox flow."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    # Show all pathways with DTMF data
    user = TelegramUser.objects.filter(user_id=user_id).first()
    if not user:
        bot.send_message(user_id, "No keypress responses found.")
        return

    dtmf_records = DTMF_Inbox.objects.filter(user_id=user).values_list("pathway_id", flat=True).distinct()
    if not dtmf_records:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="inbox_hub_back"))
        bot.send_message(user_id, "🔢 No keypress responses yet.", reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup()
    for pathway_id in dtmf_records:
        try:
            pathway = Pathways.objects.get(pathway_id=pathway_id)
            name = pathway.pathway_name
        except Pathways.DoesNotExist:
            name = pathway_id[:20]
        markup.add(types.InlineKeyboardButton(
            f"🔢 {name}", callback_data=f"dtmf_flow_{pathway_id}"
        ))
    markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="inbox_hub_back"))
    bot.send_message(user_id, "🔢 *Keypress Responses by Script*\nSelect a script:", reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dtmf_flow_"))
def handle_dtmf_flow_detail(call):
    """Show DTMF records for a specific flow."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    pathway_id = call.data.replace("dtmf_flow_", "")

    user = TelegramUser.objects.filter(user_id=user_id).first()
    records = DTMF_Inbox.objects.filter(user_id=user, pathway_id=pathway_id).order_by("-timestamp")[:10]

    if not records:
        bot.send_message(user_id, "No keypress records for this script.")
        return

    lines = ["🔢 *Keypress Responses*\n"]
    for r in records:
        date_str = r.timestamp.strftime("%b %d, %H:%M") if r.timestamp else ""
        phone = r.call_number or "Unknown"
        dtmf = r.dtmf_input or "—"
        lines.append(f"📞 `{phone}` — Input: *{dtmf}* — {date_str}")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"🔙 {BACK_BTN[lg]}", callback_data="dtmf_responses_hub"))
    bot.send_message(user_id, "\n".join(lines), reply_markup=markup, parse_mode="Markdown")


# Navigation back handlers for new hubs
@bot.callback_query_handler(func=lambda call: call.data == "inbox_hub_back")
def handle_inbox_hub_back(call):
    """Go back to Inbox hub."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_inbox_hub_keyboard
    bot.send_message(
        user_id,
        f"📬 *{INBOX_MENU[lg]}*\n\n{INBOX_HUB[lg]}",
        reply_markup=get_inbox_hub_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data == "wallet_hub_back")
def handle_wallet_hub_back(call):
    """Go back to Wallet & Billing hub."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_wallet_billing_keyboard
    wallet = check_user_balance(user_id)
    balance = wallet.get("data", {}).get("amount", 0) if wallet.get("data") else 0
    bot.send_message(
        user_id,
        f"💰 *{WALLET_AND_BILLING[lg]}*\n\n💵 Balance: *${balance}*",
        reply_markup=get_wallet_billing_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data == "phone_hub_back")
def handle_phone_hub_back(call):
    """Go back to Phone Numbers hub."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    from bot.keyboard_menus import get_phone_numbers_hub_keyboard
    bot.send_message(
        user_id,
        f"📞 *{PHONE_NUMBERS_MENU[lg]}*\n\n{PHONE_NUMBERS_HUB[lg]}",
        reply_markup=get_phone_numbers_hub_keyboard(user_id),
        parse_mode="Markdown",
    )


# --- Onboarding: Free Plan Auto-Activate & How It Works ---

@bot.callback_query_handler(func=lambda call: call.data == "activate_free_plan")
def handle_activate_free_plan(call):
    """Auto-activate the free plan and send to main menu."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    user = TelegramUser.objects.get(user_id=user_id)

    # Find the Free plan
    free_plan = SubscriptionPlans.objects.filter(name="Free").first()
    if free_plan:
        try:
            sub = UserSubscription.objects.get(user_id=user_id)
            if sub.subscription_status == "active" and sub.plan_id:
                bot.send_message(user_id, f"You already have an active plan: *{sub.plan_id.name}*", parse_mode="Markdown")
                send_welcome(call.message)
                return
        except UserSubscription.DoesNotExist:
            pass

        # set_user_subscription expects the TelegramUser object and plan_id string
        result = set_user_subscription(user, str(free_plan.plan_id))
        if result == "200":
            bot.send_message(user_id, f"🎉 {FREE_PLAN_ACTIVATED[lg]}")
        else:
            bot.send_message(user_id, f"Could not activate free plan: {result}")
    else:
        bot.send_message(user_id, "Free plan not available. Please choose a premium plan.")
        handle_activate_subscription(call)
        return

    # Offer the First Call Wizard
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"📞 {WIZARD_TRY_CALL[lg]}", callback_data="wizard_start"
    ))
    markup.add(types.InlineKeyboardButton(
        f"⏭ {WIZARD_SKIP[lg]}", callback_data="wizard_skip"
    ))
    bot.send_message(user_id, f"🎯 {WIZARD_OFFER[lg]}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "wizard_skip")
def handle_wizard_skip(call):
    """Skip wizard, go to main menu."""
    send_welcome(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "wizard_start")
def handle_wizard_start(call):
    """Start the first-call wizard — ask for phone number."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "wizard_phone"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("Cancel"))
    bot.send_message(user_id, f"📞 {WIZARD_ENTER_PHONE[lg]}", reply_markup=markup)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "wizard_phone"
)
def handle_wizard_phone(message):
    """Receive phone number and place the test call."""
    user_id = message.chat.id
    lg = get_user_language(user_id)

    if message.text and message.text.lower() == "cancel":
        user_data[user_id]["step"] = ""
        bot.send_message(user_id, CANCEL_CONFIRM[lg], reply_markup=get_main_menu_keyboard(user_id))
        return

    phone = message.text.strip() if message.text else ""
    if not validate_mobile(phone):
        bot.send_message(
            user_id,
            "Please enter a valid phone number with country code (e.g., +14155552671).",
        )
        return

    user_data[user_id]["step"] = ""
    bot.send_message(user_id, f"📲 {WIZARD_CALLING[lg]}", reply_markup=types.ReplyKeyboardRemove())

    # Get a shared caller ID (admin number) if available
    admin_users = TelegramUser.objects.filter(is_admin=True).values_list("user_id", flat=True)
    caller_id = None
    if admin_users:
        admin_num = UserPhoneNumber.objects.filter(
            user__user_id__in=admin_users, is_active=True
        ).first()
        if admin_num:
            caller_id = admin_num.phone_number

    # Place the test call
    try:
        response, status_code = make_wizard_test_call(
            phone_number=phone,
            user_id=user_id,
            caller_id=caller_id,
        )
        if status_code == 200 or status_code == 201:
            bot.send_message(
                user_id, WIZARD_SUCCESS[lg],
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                user_id, WIZARD_FAILED[lg],
                reply_markup=get_main_menu_keyboard(user_id),
            )
    except Exception as e:
        _handler_logger.error(f"Wizard call failed: {e}")
        bot.send_message(
            user_id, WIZARD_FAILED[lg],
            reply_markup=get_main_menu_keyboard(user_id),
        )


@bot.callback_query_handler(func=lambda call: call.data == "how_it_works")
def handle_how_it_works(call):
    """Show how Speechcue works."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"🔙 {MAIN_MENU_BTN[lg]}", callback_data="back_to_welcome_message"
    ))
    bot.send_message(user_id, HOW_IT_WORKS_TEXT[lg], reply_markup=markup, parse_mode="Markdown")

# :: TRIGGERS ------------------------------------#


@bot.message_handler(func=lambda message: message.text in JOIN_CHANNEL.values())
def handle_join_channel(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        f"{JOIN_CHANNEL_PROMPT[lg]}\n {CHANNEL_LINK}",
        reply_markup=support_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in PROFILE.values())
def get_user_profile(message):
    user_id = message.chat.id
    user = TelegramUser.objects.get(user_id=message.chat.id)
    lg = get_user_language(user_id)
    bot.send_message(user_id, f"{PROFILE_INFORMATION_PROMPT[lg]}")
    username_formated = user.user_name.replace("_", "\\_")
    bot.send_message(
        user_id, f"{USERNAME[lg]} : {username_formated}", parse_mode="Markdownv2"
    )
    user_plan = UserSubscription.objects.get(user_id=user.user_id)
    if user_plan.subscription_status == f"{INACTIVE[lg]}":
        bot.send_message(user_id, f"{NO_SUBSCRIPTION_PLAN[lg]}")
    else:
        plan_msg = (
            f"{SUBSCRIPTION_PLAN[lg]}: \n"
            f"{NAME[lg]} :{user_plan.plan_id.name}\n"
            f"{BULK_IVR_LEFT[lg]} : {user_plan.bulk_ivr_calls_left}\n"
        )
        if user_plan.single_ivr_left != MAX_INFINITY_CONSTANT:
            plan_msg += f"{SINGLE_CALLS_LEFT[lg]}{user_plan.single_ivr_left}\n"
        bot.send_message(user_id, plan_msg)
    wallet = check_user_balance(user_id)
    balance = wallet["data"]["amount"]
    bot.send_message(
        user_id,
        f"{BALANCE_IN_USD[lg]}{balance}",
        reply_markup=account_keyboard(user_id),
    )
    bot.send_message(
        user_id,
        SELECTION_PROMPT[lg],
        reply_markup=account_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text == "Back 📞")
def handle_back_ivr_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        FLOW_OPERATIONS_SELECTION_PROMPT[lg],
        reply_markup=advanced_user_flow_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text == "Back 📲")
def handle_back_ivr_call(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        FLOW_OPERATIONS_SELECTION_PROMPT[lg],
        reply_markup=ivr_call_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in HELP.values())
def handle_help(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    commands = f"- {CREATE_IVR_FLOW[lg]}\n- {VIEW_FLOWS[lg]}\n- {DELETE_FLOW[lg]}\n"
    bot.send_message(
        user_id,
        f"{AVAILABLE_COMMANDS_PROMPT[lg]}\n"
        f"{VIEW_COMMANDS_IN_MAIN_MENU[lg]}\n"
        f"{REQUIRED_TO_SIGN_UP[lg]}\n{commands}",
        reply_markup=support_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text == "Back 👤")
def back_support(message):
    display_support_menu(message)


@bot.message_handler(commands=["help"])
def show_available_commands(message):
    handle_help(message)


@bot.callback_query_handler(func=lambda call: call.data == "help")
def handle_help_callback(call):
    handle_help(call.message)


@bot.message_handler(
    func=lambda message: message.text in BILLING_AND_SUBSCRIPTION.values()
)
def trigger_billing_and_subscription(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        f"{SELECTION_PROMPT[lg]}",
        reply_markup=get_billing_and_subscription_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in SETTINGS.values())
def trigger_settings(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECTION_PROMPT[lg], reply_markup=get_setting_keyboard(user_id)
    )


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
def handle_language_update_settings(call):
    user_id = call.from_user.id
    selected_language = call.data.split(":")[1]
    print(f"[SETTINGS] language update: {selected_language}")
    user = TelegramUser.objects.get(user_id=user_id)
    user.language = selected_language
    user.save()
    if user_id not in user_data:
        user_data[user_id] = {}
    reset_user_language(user_id)
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        LANGUAGE_CHANGED_SUCCESSFULLY[lg],
        reply_markup=get_setting_keyboard(user_id),
    )


@bot.callback_query_handler(func=lambda call: call.data == "view_subscription")
def handle_view_subscription(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    try:
        user = UserSubscription.objects.get(user_id=user_id)
        print(user.subscription_status, "subscription status ")
        if user.subscription_status == f"{INACTIVE[lg]}":
            bot.send_message(
                user_id,
                f"{NO_SUBSCRIPTION_PLAN[lg]}",
                reply_markup=get_billing_and_subscription_keyboard(user_id),
            )
            return
        plan = user.plan_id_id
        print("User Plan: ", plan)

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
            reply_markup=get_billing_and_subscription_keyboard(user_id),
        )

    except TelegramUser.DoesNotExist:
        bot.send_message(
            user_id,
            f"{SUBSCRIPTION_PLAN_NOT_FOUND[lg]}",
            reply_markup=get_billing_and_subscription_keyboard(user_id),
        )

    except SubscriptionPlans.DoesNotExist:
        bot.send_message(
            user_id,
            f"{NO_SUBSCRIPTION_PLAN[lg]}",
            reply_markup=get_billing_and_subscription_keyboard(user_id),
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
        if wallet["status"] != 200:
            bot.send_message(user_id, f"{WALLET_DETAILS_ERROR[lg]}")
            return
        balance = wallet["data"]["amount"]
        currency = wallet["data"]["currency"]
        markup = InlineKeyboardMarkup()
        top_up_wallet_button = types.InlineKeyboardButton(
            TOP_UP[lg], callback_data="top_up_wallet"
        )
        back_button = types.InlineKeyboardButton(
            BACK[lg], callback_data="back_to_billing"
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
        reply_markup=get_billing_and_subscription_keyboard(user_id),
    )


@bot.message_handler(
    func=lambda message: message.text in ADD_ANOTHER_PHONE_NUMBER.values()
)
def trigger_yes(message):
    user_id = message.chat.id
    number = user_data[user_id]["batch_numbers"]
    data = {"phone_number": f"{number}"}
    call_data.append(data)


@bot.message_handler(func=lambda message: message.text in TEXT_TO_SPEECH.values())
def trigger_text_to_speech(message):
    handle_get_node_type(message)


# @bot.message_handler(func=lambda message: message.text in SINGLE_IVR.values())
# def trigger_single_ivr_call(message):
#     """
#     Handles the 'Single IVR Call ☎️' menu option to initiate an IVR call.
#
#     Args:
#        message: The message object from the user.
#     """
#     user_id = message.chat.id
#     user = TelegramUser.objects.get(user_id=user_id)
#     subscription = UserSubscription.objects.get(user_id=user)
#     lg = get_user_language(user_id)
#     print(f"in single ivr trigger with user id : {user_id}")
#     if subscription.subscription_status == "active":
#         bot.send_message(user_id, SUBSCRIPTION_VERIFIED[lg])
#         user_data[user_id] = {"step": "phone_number_input"}
#         view_flows(message)
#
#     else:
#         bot.send_message(
#             user_id,
#             f"{ACTIVATE_SUBSCRIPTION[lg]}",
#             reply_markup=get_subscription_activation_markup(user_id),
#         )


@bot.callback_query_handler(func=lambda call: call.data == "trigger_single_flow")
def trigger_flow_single(call):
    user_id = call.message.chat.id
    user_data[user_id] = {"step": "phone_number_input"}
    view_flows(call.message)


@bot.message_handler(func=lambda message: message.text in BACK.values())
def trigger_back_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    step = user_data[user_id]["step"]
    if step == "display_flows":
        display_flows(message)
        return
    bot.send_message(
        user_id, f"{WELCOME_PROMPT[lg]}", reply_markup=get_main_menu_keyboard(user_id)
    )


@bot.message_handler(
    func=lambda message: message.text in DONE_ADDING_NODES.values()
    or message.text in CONTINUE_ADDING_EDGES.values()
    or message.text in ADD_EDGE.values()
)
def trigger_add_edges(message):
    """
    Handles the 'Done Adding Nodes' menu option to initiate edge addition.

    Args:
        message: The message object from the user.
    """
    handle_add_edges(message)


@bot.message_handler(func=lambda message: message.text in CONFIRM_DELETE.values())
def trigger_confirmation(message):
    """
    Handles the 'Confirm Delete' menu option to confirm deletion of a pathway.
    Args:
        message: The message object from the user.
    """
    handle_get_pathway(message)


@bot.message_handler(func=lambda message: message.text in DELETE_NODE.values())
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

    # Check if no nodes are found in the pathway
    if not pathway["nodes"]:
        bot.send_message(user_id, f"{NO_NODES_FOUND[lg]}")
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


@bot.message_handler(func=lambda message: message.text in RETRY_NODE.values())
def trigger_retry_node(message):
    """
    Handles the 'Retry Node 🔄' menu option to retry a node.

    Args:
        message: The message object from the user.
    """
    bot.send_message(message.chat.id, f"{RETRY_NODE[lg]}")


@bot.message_handler(func=lambda message: message.text in SKIP_NODE.values())
def trigger_skip_node(message):
    """
    Handles the 'Skip Node ⏭️' menu option to skip a node.

    Args:
       message: The message object from the user.
    """
    bot.send_message(message.chat.id, f"{SKIP_NODE[lg]}")


@bot.message_handler(
    func=lambda message: message.text in TRANSFER_TO_LIVE_AGENT.values()
)
def trigger_transfer_to_live_agent_node(message):
    transfer_to_agent(message)


@bot.message_handler(func=lambda message: message.text in DONE_ADDING_EDGES.values())
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


@bot.message_handler(
    func=lambda message: message.text in CONTINUE_TO_NEXT_NODE.values()
)
def trigger_add_another_node(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    keyboard = check_user_has_active_free_plan(user_id)
    bot.send_message(
        message.chat.id, f"{NODE_TYPE_SELECTION_PROMPT[lg]}", reply_markup=keyboard
    )


@bot.message_handler(func=lambda message: message.text in REPEAT_MESSAGE.values())
def trigger_repeat_message(message):
    pass


@bot.message_handler(
    func=lambda message: message.text in BACK_TO_MAIN_MENU.values()
    or message.text in BACK_BUTTON.values()
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
    func=lambda message: message.text in END_CALL.values()
    or message.text in CALL_TRANSFER.values()
    or message.text in GET_DTMF_INPUT.values()
    or message.text in PLAY_MESSAGE.values()
    or message.text in MENU.values()
    or message.text in FEEDBACK_NODE.values()
    or message.text in QUESTION.values()
)
def trigger_main_add_node(message):
    add_node(message)


@bot.message_handler(func=lambda message: message.text in VIEW_VARIABLES.values())
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
            formatted_key = escape_markdown(key)
            formatted_variables.append(f"{formatted_key}: {value}")
        variable_message = "\n".join(formatted_variables)

        if not variable_message:
            msg = f"{NO_VARIABLES_FOUND[lg]} {call_id}"
            bot.send_message(user_id, escape_markdown(msg), parse_mode="MarkdownV2")
        else:
            bot.send_message(user_id, variable_message, parse_mode="MarkdownV2")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"{PROCESSING_ERROR[lg]} {str(e)}")


# @bot.message_handler(func=lambda message: message.text in USER_FEEDBACK.values())
# def view_feedback(message):
#
#     user_id = message.chat.id
#     lg = get_user_language(user_id)
#     feedback_pathway_ids = FeedbackLogs.objects.values_list("pathway_id", flat=True)
#     list_calls = CallLogsTable.objects.filter(
#         user_id=user_id, pathway_id__in=feedback_pathway_ids
#     )
#     if not list_calls.exists():
#         bot.send_message(user_id, f"{CALL_LOGS_NOT_FOUND[lg]}")
#         return
#     markup = types.InlineKeyboardMarkup()
#     for call in list_calls:
#         button_text = f"Call ID: {call.call_id}"
#         callback_data = f"feedback_{call.call_id}"
#         markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
#     markup.add(
#         types.InlineKeyboardButton(BACK_BUTTON[lg], callback_data="back_account")
#     )
#
#     bot.send_message(user_id, f"{VIEW_TRANSCRIPT_PROMPT[lg]}", reply_markup=markup)


# Define the function to handle DTMF_INBOX messages
@bot.message_handler(func=lambda message: message.text in DTMF_INBOX.values())
def handle_dtmf_inbox(message):
    lg = get_user_language(message.chat.id)
    user_id = message.chat.id
    user = TelegramUser.objects.get(user_id=user_id)
    call_numbers = (
        DTMF_Inbox.objects.filter(user_id=user)
        .values_list("call_number", flat=True)
        .distinct()
    )

    if not call_numbers:
        bot.send_message(user_id, CALL_LOGS_NOT_FOUND[lg])
        return

    # Display the list of phone numbers as an inline keyboard
    markup = types.InlineKeyboardMarkup()
    for number in call_numbers:
        button_text = f"Phone Number: {number}"
        callback_data = f"phone_{number}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    markup.add(
        types.InlineKeyboardButton(BACK[lg], callback_data="back_to_welcome_message")
    )

    bot.send_message(user_id, SELECT_PHONE_NUMBER_INBOX[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_dtmf_main")
def handle_back_dtmf_main(call):
    if call.data == "back_dtmf_main":
        handle_dtmf_inbox(call.message)
        return


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("phone_") or call.data == "back_dtmf"
)
def handle_phone_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}

    if call.data == "back_dtmf":
        phone_number = user_data[user_id]["previous_phone_number"]
    else:
        phone_number = call.data.split("phone_")[1]
        user_data[user_id]["previous_phone_number"] = phone_number

    pathways = Pathways.objects.filter(
        pathway_user_id=user_id,
        pathway_id__in=DTMF_Inbox.objects.filter(
            call_number=phone_number, user_id=user_id
        ).values_list("pathway_id", flat=True),
    )

    if not pathways.exists():
        bot.send_message(user_id, PATHWAY_NOT_FOUND[lg])
        return

    markup = types.InlineKeyboardMarkup()
    for pathway in pathways:
        button_text = f"Script: {pathway.pathway_name}"
        callback_data = f"pathway_{pathway.pathway_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

    markup.add(types.InlineKeyboardButton(BACK[lg], callback_data="back_dtmf_main"))
    bot.send_message(user_id, SELECT_PATHWAY[lg], reply_markup=markup)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("pathway_")
    or call.data.startswith("back_phone_")
)
def handle_pathway_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if call.data.startswith("back_phone_"):
        phone_number = call.data.split("back_phone_")[1]
        handle_phone_selection(
            types.CallbackQuery(call.message, data=f"phone_{phone_number}")
        )
        return

    pathway_id = call.data.split("pathway_")[1]
    user = TelegramUser.objects.get(user_id=user_id)

    # Fetch call IDs associated with the pathway ID and user ID
    call_logs = DTMF_Inbox.objects.filter(user_id=user, pathway_id=pathway_id)

    if not call_logs.exists():
        bot.send_message(user_id, CALL_LOGS_NOT_FOUND[lg])
        return

    # Display the list of call IDs as an inline keyboard
    markup = types.InlineKeyboardMarkup()
    for log in call_logs:
        button_text = f"Call ID: {log.call_id}"
        callback_data = f"call_{log.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

    markup.add(types.InlineKeyboardButton(BACK[lg], callback_data="back_dtmf"))
    bot.send_message(user_id, SELECT_CALL_ID[lg], reply_markup=markup)


# Handle call ID selection
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("call_")
    or call.data.startswith("back_pathway_")
)
def handle_call_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if call.data.startswith("back_pathway_"):
        pathway_id = call.data.split("back_pathway_")[1]
        handle_pathway_selection(
            types.CallbackQuery(call.message, data=f"pathway_{pathway_id}")
        )
        return

    call_id = call.data.split("call_")[1]
    user = TelegramUser.objects.get(user_id=user_id)

    call_log = DTMF_Inbox.objects.filter(user_id=user, call_id=call_id).first()

    if not call_log:
        bot.send_message(user_id, NO_DTMF_INPUT_FOUND[lg])
        return

    dtmf_input = call_log.dtmf_input
    phone_number = call_log.call_number
    timestamp = call_log.timestamp

    # Add back button
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(BACK[lg], callback_data="back_dtmf"))

    bot.send_message(
        user_id,
        f"{PHONE_NUMBER_TEXT[lg]}: {phone_number}\n"
        f"{DTMF_INPUT_TEXT[lg]}{dtmf_input}\n"
        f"{TIMESTAMP_TEXT[lg]}: {timestamp}",
        reply_markup=markup,
    )


def handle_back_in_user_feedback(message, bot_prompt):
    user_id = message.chat.id
    if message.text == "/start":
        user_data[user_id]["step"] = ""
        send_welcome(message)
    elif message.text == "/support":
        user_data[user_id]["step"] = ""
        display_support_menu(message)
    else:
        bot.send_message(user_id, bot_prompt)
        return


@bot.message_handler(func=lambda message: message.text in USER_FEEDBACK.values())
def initiate_date_range_search(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(user_id, START_YEAR_PROMPT[lg], reply_markup=get_force_reply())
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "start_year"


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "start_year"
)
def handle_start_year(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    try:
        year = int(message.text)
        if year < 1900 or year > datetime.now().year:
            raise ValueError("Invalid year")
        user_data[user_id]["start_year"] = year
        bot.send_message(
            user_id, START_MONTH_PROMPT[lg], reply_markup=get_force_reply()
        )
        user_data[user_id]["step"] = "start_month"
    except ValueError:

        handle_back_in_user_feedback(message, INVALID_YEAR_PROMPT[lg])


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "start_month"
)
def handle_start_month(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    try:
        month = int(message.text)
        if month < 1 or month > 12:
            raise ValueError("Invalid month")
        user_data[user_id]["start_month"] = month
        bot.send_message(user_id, START_DAY_PROMPT[lg], reply_markup=get_force_reply())
        user_data[user_id]["step"] = "start_day"
    except ValueError:
        print("message", message.text)
        handle_back_in_user_feedback(message, INVALID_MONTH_PROMPT[lg])


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "start_day"
)
def handle_start_day(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    try:
        day = int(message.text)
        year = user_data[user_id]["start_year"]
        month = user_data[user_id]["start_month"]
        if day < 1 or day > (
            29
            if month == 2 and isleap(year)
            else (28 if month == 2 else (30 if month in [4, 6, 9, 11] else 31))
        ):
            raise ValueError("Invalid day")
        user_data[user_id]["start_day"] = day
        bot.send_message(user_id, END_YEAR_PROMPT[lg], reply_markup=get_force_reply())
        user_data[user_id]["step"] = "end_year"
    except ValueError:
        print("message", message.text)
        handle_back_in_user_feedback(message, INVALID_DAY_PROMPT[lg])


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "end_year"
)
def handle_end_year(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    try:
        end_year = int(message.text)
        start_year = user_data[user_id]["start_year"]

        if end_year < start_year:
            bot.send_message(
                user_id, INVALID_YEAR_RANGE_PROMPT[lg], reply_markup=get_force_reply()
            )
            return

        user_data[user_id]["end_year"] = end_year
        bot.send_message(user_id, END_MONTH_PROMPT[lg], reply_markup=get_force_reply())
        user_data[user_id]["step"] = "end_month"
    except ValueError:
        handle_back_in_user_feedback(message, INVALID_YEAR_PROMPT[lg])


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "end_month"
)
def handle_end_month(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    try:
        end_month = int(message.text)
        end_year = user_data[user_id]["end_year"]
        start_year = user_data[user_id]["start_year"]
        start_month = user_data[user_id]["start_month"]

        if end_month < 1 or end_month > 12:
            bot.send_message(
                user_id, INVALID_MONTH_PROMPT[lg], reply_markup=get_force_reply()
            )
            return

        if end_year == start_year and end_month < start_month:
            bot.send_message(
                user_id, INVALID_MONTH_RANGE_PROMPT[lg], reply_markup=get_force_reply()
            )
            return

        user_data[user_id]["end_month"] = end_month
        bot.send_message(user_id, END_DAY_PROMPT[lg], reply_markup=get_force_reply())
        user_data[user_id]["step"] = "end_day"
    except ValueError:
        handle_back_in_user_feedback(message, INVALID_MONTH_PROMPT[lg])


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step") == "end_day"
)
def handle_end_day(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    try:
        print(f"Handling end day for user {user_id}. Current user_data: {user_data}")
        end_day = int(message.text)
        end_year = user_data[user_id]["end_year"]
        end_month = user_data[user_id]["end_month"]
        start_year = user_data[user_id]["start_year"]
        start_month = user_data[user_id]["start_month"]
        start_day = user_data[user_id]["start_day"]

        max_days = (
            29
            if end_month == 2 and isleap(end_year)
            else 28 if end_month == 2 else 30 if end_month in [4, 6, 9, 11] else 31
        )

        if end_day < 1 or end_day > max_days:
            bot.send_message(
                user_id, INVALID_DAY_PROMPT[lg], reply_markup=get_force_reply()
            )
            return

        if end_year == start_year and end_month == start_month and end_day < start_day:
            bot.send_message(
                user_id, INVALID_DAY_RANGE_PROMPT[lg], reply_markup=get_force_reply()
            )
            return

        user_data[user_id]["end_day"] = end_day

        # Create datetime objects for start and end dates
        start_date = datetime(start_year, start_month, start_day)
        end_date = datetime(end_year, end_month, end_day)

        # Format and print the date range in "date-month-year"
        date_format = "%d-%m-%Y"
        date_range = (
            f"{start_date.strftime(date_format)} to {end_date.strftime(date_format)}"
        )
        print(f"Date range for user {user_id}: {date_range}")
        bot.send_message(user_id, f"{DATE_RANGE_SELECTED[lg]} {date_range}")

        if start_date > end_date:
            bot.send_message(
                user_id, INVALID_DATE_RANGE_PROMPT[lg], reply_markup=get_force_reply()
            )
            return

        calls = CallLogsTable.objects.filter(
            user_id=user_id,
            created_at__date__range=(start_date, end_date),
        )
        if not calls.exists():
            bot.send_message(
                user_id,
                f"{NO_CALLS_FOUND[lg]}",
                reply_markup=get_main_menu_keyboard(user_id),
            )
            return

        markup = types.InlineKeyboardMarkup()
        for call in calls:
            button_text = f"Call ID: {call.call_id} ({call.created_at.date()})"
            callback_data = f"feedback_{call.call_id}"
            markup.add(
                types.InlineKeyboardButton(button_text, callback_data=callback_data)
            )

        markup.add(
            types.InlineKeyboardButton(
                BACK_BUTTON[lg], callback_data="back_to_welcome_message"
            )
        )
        bot.send_message(user_id, f"{VIEW_TRANSCRIPT_PROMPT[lg]}", reply_markup=markup)
        user_data[user_id]["step"] = ""

    except KeyError as e:
        print(f"KeyError encountered for user {user_id}: {e}")
        bot.send_message(user_id, PROCESSING_ERROR[lg])
    except ValueError:
        handle_back_in_user_feedback(message, INVALID_DATE_RANGE_PROMPT[lg])


@bot.callback_query_handler(func=lambda call: call.data.startswith("feedback_"))
def handle_call_selection(call):

    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    try:
        call_id = call.data[len("feedback_") :]
        call_log = CallLogsTable.objects.get(call_id=call_id)
        pathway_id = call_log.pathway_id
        transcript = get_transcript(call_id, pathway_id)
        print("Transcript in call selection :", transcript)
        if transcript:
            transcript_message = "\n".join(
                f"Q: {question}\nA: {answer}"
                for question, answer in zip(
                    transcript.feedback_questions, transcript.feedback_answers
                )
            )
        else:
            transcript_message = f"{TRANSCRIPT_NOT_FOUND[lg]}"
        bot.send_message(
            user_id, transcript_message, reply_markup=account_keyboard(user_id)
        )
        return
    except Exception as e:
        bot.send_message(
            call.message.chat.id,
            f"{PROCESSING_ERROR[lg]} {str(e)}",
            reply_markup=get_main_menu_keyboard(user_id),
        )


@bot.message_handler(
    func=lambda message: message.text in CREATE_IVR_FLOW.values()
    or message.text in ADVANCED_USER_FLOW.values()
)
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


@bot.message_handler(func=lambda message: message.text in VIEW_FLOWS.values())
def trigger_view_flows(message):
    """
    Handle 'View Flows 📂' menu option.
    """
    display_flows(message)


@bot.message_handler(func=lambda message: message.text in DELETE_FLOW.values())
def trigger_delete_flow(message):
    """
    Handle 'Delete Flow ❌' menu option.
    """
    delete_flow(message)


def get_first_node(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)

    # user_data[user_id]["select_language"] = lang
    first_node = user_data[user_id]["first_node"]
    if first_node:
        user_data[user_id]["message_type"] = "Play Message"
        message.text = "Play Message ▶️"
        user_data[user_id]["first_node"] = False
        bot.send_message(user_id, ADD_GREETING_NODE[lg])
        add_node(message)

    else:
        keyboard = check_user_has_active_free_plan(user_id)
        bot.send_message(user_id, NODE_TYPE_SELECTION_PROMPT[lg], reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text in ADD_NODE.values())
def view_main_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user_data[user_id]["first_node"] = False
    get_first_node(message)


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
    Sends a welcome/dashboard message when the user starts a conversation.
    For returning users: shows a quick dashboard summary.
    """
    user_id = message.chat.id
    lg = get_user_language(user_id)

    # Build dashboard summary for returning users
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        # Get plan info
        try:
            sub = UserSubscription.objects.get(user_id=user_id, subscription_status="active")
            plan_name = sub.plan_id.name if sub.plan_id else "Free"
            minutes_left = float(sub.single_ivr_left or 0) + float(sub.bulk_ivr_calls_left or 0)
            minutes_str = f"{minutes_left:.0f}"
        except UserSubscription.DoesNotExist:
            plan_name = "None"
            minutes_str = "0"

        # Get wallet balance
        wallet = check_user_balance(user_id)
        balance = wallet.get("data", {}).get("amount", 0) if wallet.get("data") else 0

        # Get phone number count
        num_count = UserPhoneNumber.objects.filter(user_id=user_id, is_active=True).count()

        dashboard = (
            f"👋 *{WELCOME_BACK[lg]}, {user.user_name or 'there'}!*\n\n"
            f"📊 *{DASHBOARD_SUMMARY[lg]}*\n"
            f"├ {PLAN_LABEL[lg]}: *{plan_name}*\n"
            f"├ {WALLET_LABEL[lg]}: *${balance}*\n"
            f"├ {NUMBERS_LABEL[lg]}: *{num_count}*\n"
            f"└ {MINUTES_LEFT_LABEL[lg]}: *{minutes_str}*"
        )
        bot.send_message(
            user_id, dashboard,
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    except TelegramUser.DoesNotExist:
        # Fallback for edge cases
        bot.send_message(
            user_id, f"{WELCOME_PROMPT[lg]}",
            reply_markup=get_main_menu_keyboard(user_id),
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
        reply_markup=get_main_menu_keyboard(user_id),
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
    user_data[user_id] = {"step": "", "name": name, "username": username}
    bot.send_message(
        user_id, f"{NICE_TO_MEET_YOU[lg]}!😊 {name}, " f"{PROFILE_SETTING_PROMPT[lg]}⏳"
    )
    # Skip email and mobile steps — auto-generate defaults
    auto_email = f"{user_id}@speechcue.bot"
    auto_mobile = "+10000000000"
    response = setup_user(user_id, auto_email, auto_mobile, name, username)
    if response["status"] != 200:
        bot.send_message(user_id, f"{REQUEST_FAILED[lg]}\n{response['text']}")
    else:
        bot.send_message(user_id, f"🎉 {SETUP_COMPLETE[lg]}")
        user_data[user_id]["step"] = ""
        handle_terms_and_conditions(message)


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
        # Pre-validation to ensure the number has only one '+' at the start
        if mobile.count("+") > 1 or (
            mobile.count("+") == 1 and not mobile.startswith("+")
        ):
            print(
                f"Number {mobile} is invalid: it contains more than one '+' or has '+' in an invalid position."
            )
            return False

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
    bot.send_message(user_id, msg, reply_markup=get_main_menu_keyboard(user_id))


@bot.message_handler(commands=["support"])
def display_support_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECTION_PROMPT[lg], reply_markup=support_keyboard(user_id)
    )


def display_main_menu(message):
    user_id = message.chat.id
    bot.send_message(
        user_id,
        "Welcome to the main menu!",
        reply_markup=get_main_menu_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in IVR_FLOW.values())
def display_ivr_flow_types(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, CHOOSE_IVR_FLOW_TYPE[lg], reply_markup=ivr_flow_keyboard(user_id)
    )


@bot.message_handler(
    func=lambda message: message.text in AI_ASSISTED_FLOW_KEYBOARD.values()
)
def display_ai_assisted_flows(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        FLOW_OPERATIONS_SELECTION_PROMPT[lg],
        reply_markup=ai_assisted_user_flow_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in CREATE_IVR_FLOW_AI.values())
def display_create_ivr_flows_ai(message):
    initiate_ai_assisted_flow(message)


@bot.message_handler(
    func=lambda message: message.text in ADVANCED_USER_FLOW_KEYBOARD.values()
)
def display_advanced_flow_keyboard(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        FLOW_OPERATIONS_SELECTION_PROMPT[lg],
        reply_markup=advanced_user_flow_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in IVR_CALL.values())
def display_ivr_calls_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id in user_data:
        user_data[user_id]["step"] = ""

    bot.send_message(
        user_id, IVR_CALL_SELECTION_PROMPT[lg], reply_markup=ivr_call_keyboard(user_id)
    )


@bot.message_handler(func=lambda message: message.text in ACCOUNT.values())
def display_account_menu(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECTION_PROMPT[lg], reply_markup=account_keyboard(user_id)
    )


@bot.message_handler(commands=["sign_up", "start"])
def language_selection(message):
    user_id = message.chat.id
    tg_username = (message.from_user.username or "").lower()
    try:
        existing_user, created = TelegramUser.objects.get_or_create(
            user_id=user_id, defaults={
                "user_name": f"{user_id}",
                "telegram_username": tg_username or None,
                "is_admin": tg_username in ADMIN_USERNAMES,
            }
        )
        # Always sync username + admin flag for returning users
        _sync_telegram_username(message.from_user)
        if not created:
            lg = get_user_language(user_id)
            print(f"lg : {lg}")
            selected_language = existing_user.language
            print("user language: ", selected_language)
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]["set_language"] = selected_language
            send_welcome(message)
            return
        # New user — clear any cached keyboard first
        bot.send_message(
            user_id,
            "Welcome! Let's get you set up.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        bot.send_message(
            user_id,
            f"🌍 {PROFILE_LANGUAGE_SELECTION_PROMPT['English']}",
            reply_markup=get_language_markup("language"),
        )
    except Exception as e:
        bot.reply_to(
            message, f"{PROCESSING_ERROR['English']} {str(e)}", reply_markup=get_force_reply()
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
    user = TelegramUser.objects.get(user_id=user_id)

    try:
        user_subscription = UserSubscription.objects.get(user_id=user_id)
        subscription_status = user_subscription.subscription_status

    except UserSubscription.DoesNotExist:

        UserSubscription.objects.create(user_id=user, subscription_status="inactive")
        subscription_status = "inactive"

    if subscription_status == "active":
        print(check_expiry_date(user_id))
        if check_expiry_date(user_id):
            active_plan = user_subscription.plan_id_id
            invoice = generate_invoice(active_plan, user_id)
            message = (
                f"{SUBSCRIPTION_WARNING_PT_1[lg]} \n"
                f"{invoice}\n\n"
                f"{SUBSCRIPTION_WARNING_PT_3[lg]} {SUBSCRIPTION_WARNING_PT_4[lg]} \n"
                f"{SUBSCRIPTION_WARNING_PT_5[lg]}\n"
                f"{SUBSCRIPTION_WARNING_PT_6[lg]}"
            )
            markup = InlineKeyboardMarkup()
            yes_btn = InlineKeyboardButton(
                YES[lg], callback_data="continue_plan_upgrade"
            )
            no_btn = InlineKeyboardButton(NO[lg], callback_data="cancel_plan_upgrade")
            markup.add(yes_btn, no_btn)

            bot.send_message(
                user_id,
                escape_markdown(message),
                reply_markup=markup,
                parse_mode="MarkdownV2",
            )
            return
    upgrade_plan_menu(call)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_plan_upgrade")
def handle_cancel_plan_upgrade(call):
    send_welcome(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "continue_plan_upgrade")
def upgrade_plan_menu(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    plans = SubscriptionPlans.objects.all()
    plan_icons = {"Free": "🎉", "Starter": "🌟", "Pro": "💎", "Business": "🚀"}
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
        BACK_BUTTON[lg], callback_data="back_to_view_terms"
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
        BACK_BUTTON[lg], callback_data="back_to_plan_names"
    )
    markup.add(back_button)
    bot.send_message(user_id, f"{message_text}\n\n", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_plan_names")
def back_to_plan_names(call):
    handle_activate_subscription(call)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_welcome_message")
def handle_back_message(call):
    send_welcome(call.message)


def generate_invoice(plan_id, user_id):
    lg = get_user_language(user_id)

    try:
        plan = SubscriptionPlans.objects.get(plan_id=plan_id)
    except SubscriptionPlans.DoesNotExist:
        bot.send_message(user_id, f"{PLAN_DOESNT_EXIST[lg]}")
        return

    node_access = (
        f"{FULL_NODE_ACCESS[lg]}"
        if plan.call_transfer
        else f"{PARTIAL_NODE_ACCESS[lg]}"
    )
    call_transfer_node = "✅" if plan.call_transfer else "❌"

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
    return invoice_message


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

    user_data[user_id]["selected_plan"] = plan
    user_data[user_id]["subscription_price"] = plan.plan_price
    user_data[user_id]["subscription_name"] = plan.name
    user_data[user_id]["subscription_id"] = plan.plan_id
    invoice_message = generate_invoice(plan.plan_id, user_id)

    if plan.plan_price == 0:
        user = TelegramUser.objects.get(user_id=user_id)
        if user.free_plan:
            user.subscription_status = "active"
            user.plan = plan.plan_id
            user.save()
            bot.send_message(
                user_id, escape_markdown(invoice_message), parse_mode="MarkdownV2"
            )
            set_subscription = set_user_subscription(user, plan.plan_id)
            if set_subscription != f"{STATUS_CODE_200}":
                bot.send_message(user_id, set_subscription)
                return
            bot.send_message(
                user_id,
                SUCCESSFUL_FREE_TRIAL_ACTIVATION[lg],
                reply_markup=get_main_menu_keyboard(user_id),
            )
        else:
            bot.send_message(user_id, NOT_ELIGIBLE_FOR_FREE_TRIAL[lg])
            handle_activate_subscription(call)
        return
    auto_renewal = escape_markdown(AUTO_RENEWAL_PROMPT[lg])
    yes = f"{YES[lg]} ✅"
    no = f"{NO[lg]} ❌"
    markup = types.InlineKeyboardMarkup()
    yes_button = types.InlineKeyboardButton(
        yes, callback_data="enable_auto_renewal_yes"
    )
    no_button = types.InlineKeyboardButton(no, callback_data="enable_auto_renewal_no")
    back_button = types.InlineKeyboardButton(
        BACK_BUTTON[lg], callback_data="back_to_plan_names"
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


def insufficient_balance_markup(user_id):
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    top_up_wallet_button = types.InlineKeyboardButton(
        TOP_UP[lg], callback_data="top_up_wallet"
    )
    payment_option_btn = types.InlineKeyboardButton(
        CHOOSE_OTHER_PAYMENT_OPTION[lg], callback_data="payment_option"
    )
    back_button = types.InlineKeyboardButton(BACK[lg], callback_data="back_to_billing")
    markup.add(top_up_wallet_button, payment_option_btn, back_button)
    return markup


def send_payment_options(user_id):
    lg = get_user_language(user_id)
    payment_message = f"💳 {SUBSCRIPTION_PAYMENT_METHOD_PROMPT[lg]}"
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    wallet_balance = f"{PAY_FROM_WALLET_BALANCE[lg]}"
    crypto = f"{PAY_FROM_CRYPTOCURRENCY[lg]}"
    wallet_button = types.KeyboardButton(wallet_balance)
    crypto_button = types.KeyboardButton(crypto)
    markup.add(wallet_button, crypto_button)
    bot.send_message(user_id, payment_message, reply_markup=markup)


@bot.message_handler(
    func=lambda message: message.text in PAY_FROM_WALLET_BALANCE.values()
)
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
            reply_markup=insufficient_balance_markup(user_id),
        )
        return
    plan_id = user_data[user_id]["subscription_id"]
    auto_renewal = user_data[user_id]["auto_renewal"]
    response = set_plan(user_id, plan_id, auto_renewal)

    if response["status"] != 200:
        bot.send_message(user_id, f"{response['message']}")
        return
    plan = SubscriptionPlans.objects.get(plan_id=plan_id)
    message = (
        f"{PLAN_SELECTED[lg]}\n"
        f"📌 {PLAN_NAME[lg]}  {plan.name}\n"
        f"🕛 {VALIDITY[lg]}   {plan.validity_days}"
    )
    bot.send_message(
        user_id,
        f"{message}\n\n{PAYMENT_SUCCESSFUL[lg]}",
        reply_markup=get_main_menu_keyboard(user_id),
    )


@bot.message_handler(
    func=lambda message: message.text in PAY_FROM_CRYPTOCURRENCY.values()
)
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
    user_data[user_id]["method"] = "cryptocurrency"
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
            user_id,
            UNSUPPORTED_CURRENCY[lg],
            reply_markup=get_main_menu_keyboard(user_id),
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
        reply_markup=get_currency_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in TOP_UP.values())
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
        BITCOIN[lg],
        ETHEREUM[lg],
        TRC_20[lg],
        ERC_20[lg],
        LITECOIN[lg],
        DOGE[lg],
        BITCOIN_HASH[lg],
        TRON[lg],
        f"{BACK_BUTTON[lg]}",
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
    lg = get_user_language(user_id)
    payment_method = call.data.split("_")[1]
    print(f"payment methoddd : {payment_method}")
    if payment_method in BACK_BUTTON.values():
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
            reply_markup=get_main_menu_keyboard(user_id),
        )
    payment_currency = user_data[user_id]["currency"]
    bot.send_message(
        user_id,
        f"{PART1_SCAN_PAYMENT_INFO[lg]} {crypto_amount} "
        f"{payment_currency} {PART2_SCAN_PAYMENT_INFO[lg]} '<code>{address}</code>' \n\n"
        f"{PART3_SCAN_PAYMENT_INFO[lg]} "
        f"{PART4_SCAN_PAYMENT_INFO[lg]}\n\n"
        f"{PART5_SCAN_PAYMENT_INFO[lg]}\n"
        f"{PART6_SCAN_PAYMENT_INFO[lg]}\n\n"
        f"<pre>{address} </pre>",
        reply_markup=get_main_menu_keyboard(user_id),
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
            
            # Use USD amount directly from DynoPay webhook (no conversion needed)
            price_in_dollar = float(data["usd_amount"])
            
            bot.send_message(user_id, DEPOSIT_SUCCESSFUL[lg])
            plan_id = TelegramUser.objects.get(user_id=user_id).plan
            plan_price = float(
                SubscriptionPlans.objects.get(plan_id=plan_id).plan_price
            )  # Convert to float if necessary
            
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
    
    # DynoPay sends back the original USD amount we requested in 'amount' field
    # Also available in meta_data['original_amount'] for redundancy
    original_usd_amount = data.get("amount") or meta_data.get("original_amount", 0)
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
        reply_markup=get_main_menu_keyboard(user_id),
    )
    return {
        "user_id": user_id,
        "auto_renewal": auto_renewal,
        "amount": paid_amount,
        "currency": paid_currency,
        "usd_amount": float(original_usd_amount),
    }


@csrf_exempt
def crypto_transaction_webhook(request):
    """DynoPay webhook for wallet top-up. Credits internal wallet on confirmation.
    Also handles auto-purchase of phone numbers when a pending purchase exists."""
    if request.method == "POST":
        try:
            data = get_webhook_data(request)
            user_id = data["user_id"]
            amount = float(data["amount"])
            currency = data["currency"]
            lg = get_user_language(user_id)

            # Use USD amount directly from DynoPay webhook (no conversion needed)
            usd_amount = float(data["usd_amount"])
            result = credit_wallet(
                int(user_id), usd_amount,
                description=f"Crypto top-up: {amount} {currency} (${usd_amount:.2f} USD)",
            )
            if result["status"] == 200:
                bot.send_message(user_id, f"{TOP_UP_SUCCESSFUL[lg]} (+${usd_amount:.2f})")

                # Check for pending phone number purchase and auto-execute
                _fulfill_pending_phone_purchase(int(user_id))

            else:
                bot.send_message(user_id, f"{PROCESSING_ERROR[lg]}\n{result.get('message', '')}")
            return JsonResponse({"status": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": INVALID_JSON}, status=400
            )

    return JsonResponse({"status": "error", "message": METHOD_NOT_ALLOWED}, status=405)


def _fulfill_pending_phone_purchase(user_id):
    """Check for and fulfill any pending phone number purchase after crypto wallet credit."""
    pending = PendingPhoneNumberPurchase.objects.filter(
        user__user_id=user_id, is_fulfilled=False, is_failed=False
    ).order_by("created_at").first()

    if not pending:
        return  # No pending purchase

    lg = get_user_language(user_id)
    cost = float(pending.monthly_cost)

    # Check wallet has enough balance
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        if float(user.wallet_balance) < cost:
            bot.send_message(
                user_id,
                f"⚠️ Wallet credited but insufficient for phone number purchase.\n"
                f"Need: ${cost:.2f} | Balance: ${user.wallet_balance:.2f}\n"
                f"Please top up more to complete the purchase.",
            )
            return
    except TelegramUser.DoesNotExist:
        return

    bot.send_message(user_id, "⏳ Auto-purchasing your phone number... Please wait.")

    # Debit wallet
    from payment.views import debit_wallet
    debit_result = debit_wallet(
        user_id, cost,
        description=f"Phone number purchase ({pending.country_code})",
        tx_type="SUB",
    )
    if debit_result["status"] != 200:
        pending.is_failed = True
        pending.failure_reason = f"Wallet debit failed: {debit_result.get('message', '')}"
        pending.save()
        bot.send_message(
            user_id,
            f"Phone number purchase failed: {debit_result['message']}",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return

    # Purchase from Retell
    nickname = f"user_{user_id}"
    retell_result = purchase_phone_number(
        area_code=pending.area_code,
        country_code=pending.country_code,
        toll_free=pending.is_toll_free,
        nickname=nickname,
    )

    if not retell_result:
        # Refund wallet
        refund_wallet(user_id, cost, description="Phone number purchase failed — refund")
        pending.is_failed = True
        pending.failure_reason = "Retell API purchase failed"
        pending.save()
        bot.send_message(
            user_id,
            "Failed to purchase number from provider. Wallet has been refunded.\n"
            "Please try again via /start > Buy Number.",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return

    # Save to database
    from django.utils import timezone as tz
    from dateutil.relativedelta import relativedelta

    now = tz.now()
    user_obj = TelegramUser.objects.get(user_id=user_id)
    phone_record = UserPhoneNumber.objects.create(
        user=user_obj,
        phone_number=retell_result.phone_number,
        country_code=pending.country_code,
        area_code=pending.area_code,
        is_toll_free=pending.is_toll_free,
        nickname=nickname,
        monthly_cost=cost,
        next_renewal_date=now + relativedelta(months=1),
        is_active=True,
        auto_renew=True,
    )

    # Bind agent
    try:
        from bot.models import Pathways
        user_pathway = Pathways.objects.filter(user_id=user_obj).first()
        if user_pathway:
            update_phone_number_agent(
                retell_result.phone_number,
                outbound_agent_id=user_pathway.pathway_id,
                nickname=nickname,
            )
    except Exception as e:
        logger.warning(f"Agent binding skipped for auto-purchase {retell_result.phone_number}: {e}")

    # Mark fulfilled
    pending.is_fulfilled = True
    pending.save()

    bot.send_message(
        user_id,
        f"✅ *Phone Number Auto-Purchased!*\n\n"
        f"📞 Your number: `{retell_result.phone_number}`\n"
        f"🌍 Country: {pending.country_code}\n"
        f"💰 Cost: ${cost:.2f}/month (auto-renew from wallet)\n"
        f"📅 Next renewal: {phone_record.next_renewal_date.strftime('%Y-%m-%d')}\n\n"
        f"This number will now appear in your caller ID selection.",
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="Markdown",
    )


def make_payment(user_id, amount):
    lg = get_user_language(user_id)
    currency = user_data[user_id]["currency"]
    top_up = False
    redirect_uri = f"{webhook_url}/webhook/crypto_deposit"
    tx_type = user_data[user_id].get("transaction_type", "payment")

    if tx_type == "top_up":
        top_up = True
        redirect_uri = f"{webhook_url}/webhook/crypto_transaction"
    elif tx_type == "buy_number":
        # For phone number purchase via crypto: credit wallet, then auto-purchase
        top_up = True
        redirect_uri = f"{webhook_url}/webhook/crypto_transaction"

        # Save purchase intent to DB so webhook can auto-trigger purchase
        try:
            user_obj = TelegramUser.objects.get(user_id=user_id)
            PendingPhoneNumberPurchase.objects.create(
                user=user_obj,
                country_code=user_data[user_id].get("buy_number_country", "US"),
                area_code=user_data[user_id].get("buy_number_area_code"),
                is_toll_free=user_data[user_id].get("buy_number_toll_free", False),
                monthly_cost=user_data[user_id].get("buy_number_cost", PHONE_NUMBER_MONTHLY_COST_LOCAL),
            )
        except Exception as e:
            logger.error(f"Failed to save pending purchase for user {user_id}: {e}")

    auto_renewal = False
    try:
        auto_renewal = UserSubscription.objects.get(user_id=user_id).auto_renewal
    except UserSubscription.DoesNotExist:
        pass

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

    if tx_type == "buy_number":
        bot.send_message(
            user_id,
            "💎 After crypto payment is confirmed, your wallet will be credited "
            "and the phone number will be purchased automatically.\n",
        )

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
            reply_markup=advanced_user_flow_keyboard(user_id),
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
    markup.add(InlineKeyboardButton(BACK_BUTTON[lg], callback_data="back_ivr_flow"))
    bot.send_message(message.chat.id, DISPLAY_IVR_FLOWS[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_ivr_flow")
def trigger_back_ivr_flow(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        FLOW_OPERATIONS_SELECTION_PROMPT[lg],
        reply_markup=advanced_user_flow_keyboard(user_id),
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_ivr_call")
def trigger_back_ivr_call(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        IVR_CALL_SELECTION_PROMPT[lg],
        reply_markup=ivr_call_keyboard(user_id),
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_account")
def trigger_back_account(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECTION_PROMPT[lg], reply_markup=account_keyboard(user_id)
    )


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
    user_data[user_id]["select_pathway"] = pathway_id
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    user_data[user_id]["pathway_name"] = pathway.pathway_name
    pathway, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {pathway.get('error')}",
            reply_markup=advanced_user_flow_keyboard(user_id),
        )
        return

    pathway_info = (
        f"{NAME[lg]}: {pathway.get('name')}\n"
        f"{DESCRIPTION[lg]}: {pathway.get('description')}\n\n"
    ) + "\n".join(
        [f"\n  {NAME[lg]}: {node['data']['name']}\n" for node in pathway["nodes"]]
    )
    user_data[user_id]["step"] = "display_flows"

    bot.send_message(user_id, pathway_info, reply_markup=get_flow_node_menu(user_id))


@bot.message_handler(func=lambda message: message.text in CUSTOM_MADE_TASKS.values())
def view_flows(message):
    """
    Handle '/list_flows' command to retrieve all pathways.

    """
    user_id = message.chat.id
    lg = get_user_language(user_id)
    call_type = user_data[user_id]["call_type"]
    if call_type == "bulk_ivr":
        additional_minutes_records = CallDuration.objects.filter(
            user_id=user_id, additional_minutes__gt=0
        )
        if additional_minutes_records.exists():
            unpaid_minutes_records = additional_minutes_records.filter(charged=False)
            if unpaid_minutes_records.exists():
                bot.send_message(
                    user_id,
                    f"{UNPAID_MINUTES_PROMPT[lg]}",
                    reply_markup=ivr_call_keyboard(user_id),
                )
                return

    pathways, status_code = handle_view_flows()
    if status_code != 200:
        bot.send_message(
            user_id,
            f"{PROCESSING_ERROR[lg]} {pathways.get('error')}",
            reply_markup=advanced_user_flow_keyboard(user_id),
        )
        return
    if user_id not in user_data:
        user_data[user_id] = {}
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
            InlineKeyboardButton(CREATE_IVR_FLOW[lg], callback_data="create_ivr_flow")
        )
        if step == "phone_number_input":
            callback = "back_ivr_call"
        else:
            callback = "back_ivr_flow"
        markup.add(InlineKeyboardButton(BACK_BUTTON[lg], callback_data=callback))
        bot.send_message(message.chat.id, SELECT_IVR_FLOW[lg], reply_markup=markup)
    else:
        markup.add(
            InlineKeyboardButton(CREATE_IVR_FLOW[lg], callback_data="create_ivr_flow")
        )
        if step == "phone_number_input":
            callback = "back_ivr_call"
        else:
            callback = "back_ivr_flow"
        markup.add(InlineKeyboardButton(BACK_TO_MAIN_MENU[lg], callback_data=callback))
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

        get_first_node(message)

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
    user_id = message.chat.id
    lg = get_user_language(user_id)
    message.text = END_CALL[lg]
    add_node(message)


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
            reply_markup=advanced_user_flow_keyboard(user_id),
        )


def node_authorization_check(user_id, pathway_id):
    call_transfer = UserSubscription.objects.get(user_id=user_id).call_transfer
    print(f"Call transfer for the user : {call_transfer}")

    if call_transfer:
        return True, 200

    # Get pathway details
    pathway_details, status_code = handle_view_single_flow(pathway_id)

    if status_code != 200:
        return False, status_code

    print(f"Pathway details:\n{pathway_details}")

    # Check if there is any node of type 'Transfer Call'
    for node in pathway_details.get("nodes", []):
        if node.get("type") == "Transfer Call":
            return False, 200

    # If no 'Transfer Call' node is found
    return True, 200


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_pathway_"))
def handle_pathway_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    pathway_id = call.data.split("_")[-1]
    pathway_id = UUID(pathway_id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]["select_pathway"] = pathway_id
    if "step" in user_data.get(user_id, {}):
        check_delete = user_data[user_id]["step"]

    if check_delete == "get_pathway":
        user_data[user_id]["step"] = "back_delete_flow"
        bot.send_message(
            user_id,
            DELETE_FLOW_CONFIRMATION[lg],
            reply_markup=get_delete_confirmation_keyboard(user_id),
        )
        return

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
    elif step == "phone_number_input":
        print("phone numbers ")
        user_data[user_id]["call_flow"] = pathway_id
        user_data[user_id]["pathway_id"] = pathway_id
        # user_data[user_id]["step"] = "initiate_call"
        check, status_code = node_authorization_check(user_id, pathway_id)
        if not check:
            if status_code != 200:
                bot.send_message(
                    user_id,
                    f"{error[lg]} {TRY_AGAIN[lg]}",
                    reply_markup=ivr_call_keyboard(user_id),
                )
            else:
                bot.send_message(
                    user_id,
                    f"{UNAUTHORIZED_NODE_ACCESS[lg]}",
                    reply_markup=ivr_call_keyboard(user_id),
                )
            return
        user_data[user_id]["step"] = "get_single_call_recipient"
        bot.send_message(
            user_id, SINGLE_IVR_RECIPIENT_PROMPT[lg], reply_markup=get_force_reply()
        )

    elif step == "get_batch_numbers":
        print("get batch numbers")
        user_data[user_id]["call_flow_bulk"] = pathway_id
        user_data[user_id]["pathway_id"] = pathway_id
        check, status_code = node_authorization_check(user_id, pathway_id)
        if not check:
            if status_code != 200:
                bot.send_message(
                    user_id,
                    f"{error[lg]} {TRY_AGAIN[lg]}",
                    reply_markup=ivr_call_keyboard(user_id),
                )
            else:
                bot.send_message(
                    user_id,
                    f"{UNAUTHORIZED_NODE_ACCESS[lg]}",
                    reply_markup=ivr_call_keyboard(user_id),
                )
            handle_bulk_ivr_flow_call(call.message)
            return
        user_data[user_id]["step"] = "campaign_name"
        bot.send_message(
            user_id, CAMPAIGN_NAME_PROMPT[lg], reply_markup=get_force_reply()
        )


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
            reply_markup=get_main_menu_keyboard(chat_id),
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
    if not nodes:
        bot.send_message(chat_id, NO_NODES_FOUND[lg])
        return
    if len(nodes) == 1:
        bot.send_message(
            chat_id,
            ONLY_ONE_NODE_FOUND[lg],
            reply_markup=advanced_user_flow_keyboard(chat_id),
        )
        return

    if not edges:
        if start_node:
            bot.send_message(chat_id, EDGES_LIST_EMPTY[lg])

            user_data[chat_id]["source_node_id"] = f"{start_node['id']}"
            bot.send_message(
                chat_id,
                f"{START_NODE_ID[lg]} {start_node['id']}\n"
                f"{START_NODE_NAME[lg]} {start_node['data']['name']}\n",
            )
            markup = types.InlineKeyboardMarkup()
            for i in range(0, 10):
                markup.add(
                    types.InlineKeyboardButton(
                        f"Input = {i}", callback_data=f"data_user_pressed_{i}"
                    )
                )
            custom_condition = types.InlineKeyboardButton(
                CUSTOM_CONDITION[lg], callback_data="custom_condition"
            )
            markup.add(custom_condition)
            bot.send_message(chat_id, SELECT_CONDITION[lg], reply_markup=markup)
        else:
            bot.send_message(chat_id, NO_START_NODE_FOUND[lg])
            display_flows(message)
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
    nodes = user_data[user_id]["node_info"]
    source_node_id = call.data.split("_")[2]
    user_data[call.message.chat.id]["source_node_id"] = source_node_id

    selected_node = next(node for node in nodes if node["id"] == source_node_id)
    bot.send_message(
        user_id,
        f"{SOURCE_NODE[lg]} {selected_node['data']['name']} ({selected_node['id']}) {SELECTED[lg]}",
    )

    markup = types.InlineKeyboardMarkup()
    for i in range(0, 10):
        markup.add(
            types.InlineKeyboardButton(
                f"{INPUT[lg]} = {i}", callback_data=f"data_user_pressed_{i}"
            )
        )
    custom_condition = types.InlineKeyboardButton(
        CUSTOM_CONDITION[lg], callback_data="custom_condition"
    )
    markup.add(custom_condition)
    bot.send_message(user_id, SELECT_CONDITION[lg], reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "custom_condition")
def custom_condition_prompt(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    user_data[user_id]["step"] = "custom_conditions"
    bot.send_message(
        user_id, CUSTOM_CONDITION_PROMPT[lg], reply_markup=get_force_reply()
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "custom_conditions"
)
def handle_custom_conditions(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    condition = message.text
    user_data[user_id]["selected_condition"] = condition
    bot.send_message(user_id, f"{CONDITION[lg]} '{condition}'")
    send_target_nodes(user_id)


def replace_underscores_with_spaces(input_string):
    return input_string.replace("_", " ")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("data_user_pressed_")
)
def handle_condition_selection(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    condition = call.data.split("_")[-1]
    print(f"Condition: {condition}")
    formatted_condition = f"User pressed {condition}"
    print(f"Formatted Condition: {formatted_condition}")
    user_data[user_id]["selected_condition"] = formatted_condition

    bot.send_message(
        user_id, f"{CONDITION[lg]} '{INPUT[lg]} = {condition}' {SELECTED[lg]}"
    )
    send_target_nodes(user_id)


def send_target_nodes(user_id):
    lg = get_user_language(user_id)
    nodes = user_data[user_id]["node_info"]
    source_node_id = user_data[user_id]["source_node_id"]
    markup = types.InlineKeyboardMarkup()
    for node in nodes:
        if node["id"] != source_node_id:
            markup.add(
                types.InlineKeyboardButton(
                    f"{node['data']['name']} ({node['id']})",
                    callback_data=f"target_node_{node['id']}",
                )
            )
    bot.send_message(user_id, f"{SELECT_TARGET_NODE[lg]}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("target_node_"))
def handle_target_node(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    target_node_id = call.data.split("_")[2]
    nodes = user_data[user_id]["node_info"]
    source_node_id = user_data[user_id]["source_node_id"]
    condition = user_data[user_id]["selected_condition"]
    user_data[user_id]["target_node_id"] = target_node_id
    print("target node id ", target_node_id)

    target_node = next(node for node in nodes if node["id"] == target_node_id)
    source_node = next(node for node in nodes if node["id"] == source_node_id)
    response = update_edge(user_id)

    if response.status_code == 200:
        update_edges_database(user_id, response.text)
        edges_complete = edges_complete_options(user_id)
        if call.message.text not in edges_complete:
            user_data[user_id]["step"] = "error_edges_complete"
    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {response}")

    bot.send_message(
        user_id,
        f"{SOURCE_NODE[lg]} '{source_node['data']['name']} ({source_node['id']})' ->"
        f" {CONDITION[lg]} '{INPUT[lg]} = {condition}' -> {TARGET_NODE[lg]} '{target_node['data']['name']}"
        f" ({target_node['id']})' {ADDED_SUCCESSFULLY[lg]}",
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Yes", callback_data="add_another_condition"),
        types.InlineKeyboardButton("No", callback_data="save_conditions"),
    )
    bot.send_message(user_id, ADD_ANOTHER_CONDITION[lg], reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "add_another_condition")
def handle_add_another_condition(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    markup = types.InlineKeyboardMarkup()
    for i in range(0, 10):
        markup.add(
            types.InlineKeyboardButton(
                f"Input = {i}", callback_data=f"data_user_pressed_{i}"
            )
        )
    custom_condition = types.InlineKeyboardButton(
        CUSTOM_CONDITION[lg], callback_data="custom_condition"
    )
    markup.add(custom_condition)
    bot.send_message(user_id, SELECT_CONDITION[lg], reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "save_conditions")
def handle_save_conditions(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        CONTINUE_ADDING_EDGES_PROMPT[lg],
        reply_markup=edges_complete_menu(user_id),
    )
    bot.answer_callback_query(call.id)


def update_edges_database(user_id, payload):
    data = user_data[user_id]["data"]
    pathway_id = user_data[user_id]["select_pathway"]
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    pathway.pathway_name = data.get("name")
    pathway.pathway_description = data.get("description")
    pathway.pathway_payload = payload
    pathway.save()


def update_edge(chat_id):
    nodes = user_data[chat_id]["node_info"]
    edges = user_data[chat_id]["edge_info"]
    source_node_id = user_data[chat_id]["source_node_id"]
    data = user_data[chat_id]["data"]
    pathway_id = user_data[chat_id]["select_pathway"]
    target_node_id = user_data[chat_id]["target_node_id"]
    condition = user_data[chat_id]["selected_condition"]

    new_edge = {
        "id": f"reactflow__edge-{generate_random_id()}",
        "label": f"{condition}",
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
    print(f"Response : {response.text}")
    return response


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "error_edges_complete"
)
def error_edges_complete(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, MENU_SELECT[lg], reply_markup=edges_complete_menu(user_id)
    )


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
    user_data[user_id]["dtmf"] = False

    if node in PLAY_MESSAGE.values():
        user_data[user_id]["message_type"] = "Play Message"

        text_to_speech(message)

    elif node in END_CALL.values():
        user_data[user_id]["message_type"] = "End Call"
        text_to_speech(message)

    elif node in GET_DTMF_INPUT.values():
        user_data[user_id]["step"] = "get_dtmf_input"
        user_data[user_id]["dtmf"] = True
        user_data[user_id]["message_type"] = "DTMF Input"
        bot.send_message(user_id, DTMF_PROMPT[lg], reply_markup=get_force_reply())

    elif node in CALL_TRANSFER.values():
        user_data[user_id]["step"] = "get_transfer_call_prompt"
        user_data[user_id]["message_type"] = "Transfer Call"
        bot.send_message(
            user_id,
            f"{ENTER_MESSAGE_PROMPT[lg]} Transfer Call: ",
            reply_markup=get_force_reply(),
        )

    elif node in MENU.values():
        user_data[user_id]["step"] = "get_menu"
        bot.send_message(
            user_id, PROMPT_MESSAGE_FOR_MENU[lg], reply_markup=get_force_reply()
        )

    elif node in FEEDBACK_NODE.values():
        user_data[user_id]["message_type"] = "Feedback Node"
        text_to_speech(message)

    elif node in QUESTION.values():
        user_data[user_id]["message_type"] = "Question"
        text_to_speech(message)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_transfer_call_prompt"
)
def handle_get_transfer_call_prompt(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user_data[user_id]["transfer_call_text"] = message.text
    message_type = user_data[user_id]["message_type"]
    user_data[user_id]["step"] = "get_dtmf_input"
    bot.send_message(
        user_id,
        ENTER_PHONE_NUMBER_FOR_CALL_TRANSFER[lg],
        reply_markup=get_force_reply(),
    )


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
            reply_markup=get_node_complete_menu(user_id),
        )
        node_complete = node_complete_options(user_id)
        if message.text not in node_complete:
            user_data[user_id]["step"] = "error_nodes_complete"
    else:
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {response}")


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "error_nodes_complete"
)
def error_nodes_complete(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECT_FROM_MENU[lg], reply_markup=get_node_complete_menu(user_id)
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
        reply_markup=get_play_message_input_type(user_id),
    )
    message_input_type = get_message_input_type_list(user_id)
    if message.text not in message_input_type:
        user_data[user_id]["step"] = "error_message_input_type"


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "error_message_input_type"
)
def error_message_input_type(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    message_input_type = get_message_input_type_list(user_id)
    if message.text in message_input_type:
        user_data[user_id]["step"] = "get_node_type"
        return

    bot.send_message(
        user_id, SELECTION_PROMPT[lg], reply_markup=get_play_message_input_type(user_id)
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
    dtmf = user_data[user_id]["dtmf"]

    if message_type == "Transfer Call":
        if not validate_mobile(text):
            bot.send_message(user_id, INVALID_NUMBER_PROMPT[lg])
            return
        message = user_data[user_id]["transfer_call_text"]
        response = handle_transfer_call_node(
            pathway_id, node_id, prompt, node_name, message
        )
    else:
        response = handle_dtmf_input_node(pathway_id, node_id, prompt, node_name, dtmf)

    if response.status_code == 200:
        bot.send_message(
            user_id,
            f"'{node_name}'{NODE_ADDED[lg]}! ✅",
            reply_markup=get_node_complete_menu(user_id),
        )
        node_complete = node_complete_options(user_id)
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
    if node_type == TEXT_TO_SPEECH[lg]:
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
    user_data[user_id]["step"] = "select_gender"
    markup = ReplyKeyboardMarkup()
    female_btn = KeyboardButton(FEMALE[lg])
    male_btn = KeyboardButton(MALE[lg])
    markup.add(female_btn, male_btn)
    bot.send_message(user_id, GENDER_SELECTION_PROMPT[lg], reply_markup=markup)


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "select_voice_type"
)
def handle_select_voice_type(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    text = message.text
    pathway_id = user_data[user_id]["select_pathway"]
    node_name = user_data[user_id]["add_node"]
    node_text = user_data[user_id]["play_message"]
    node_id = user_data[user_id]["add_node_id"]
    if text == "Default John":
        text = "f93094fc-72ac-4fcf-9cf0-83a7fff43e88"
    # voice_data is now a list from Retell (not {"voices": [...]})
    voices = voice_data if isinstance(voice_data, list) else voice_data.get("voices", [])
    voice_type = next(
        (voice for voice in voices if voice.get("name") == text or voice.get("voice_id") == text), None
    )

    message_type = user_data[user_id]["message_type"]
    if message_type == "Question":
        response = question_type(pathway_id, node_name, node_text, node_id, voice_type)
    else:
        response = play_message(
            pathway_id,
            node_name,
            node_text,
            node_id,
            voice_type,
            message_type,
        )

    if response.status_code == 200:
        bot.send_message(
            user_id,
            f"'{node_name}' {NODE_ADDED[lg]} ✅",
            reply_markup=get_node_complete_menu(user_id),
        )
        node_complete = node_complete_options(user_id)
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
        user_id, CALL_FAILURE_PROMPT[lg], reply_markup=get_call_failed_menu(user_id)
    )
    call_failed_menu = get_call_failed_menu_list(user_id)
    if message.text not in call_failed_menu:
        user_data[user_id]["step"] = "show_error_call_failed"


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "show_error_call_failed"
)
def handle_show_error_call_failed(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, SELECT_FROM_MENU[lg], reply_markup=get_call_failed_menu(user_id)
    )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "select_gender"
)
def select_gender(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    gender = message.text
    user_data[user_id]["step"] = "select_voice_type"
    bot.send_message(
        user_id, SELECT_VOICE_TYPE_PROMPT[lg], reply_markup=get_voice_type_menu(gender)
    )


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
            reply_markup=yes_or_no(user_id),
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
    if text in YES.values():
        phone_numbers = user_data[user_id]["phone_numbers"]
        bot.send_message(
            user_id,
            SELECT_PHONE_NUMBER[lg],
            reply_markup=get_inline_keyboard(phone_numbers),
        )
        user_data[user_id]["step"] = "select_phone_number"
    elif text in NO.values():
        bot.send_message(
            user_id, ENTER_PHONE_NUMBER_TO_TRANSFER[lg], reply_markup=get_force_reply()
        )
        user_data[user_id]["step"] = "enter_new_number"
    else:
        bot.send_message(
            user_id,
            YES_OR_NO_PROMPT[lg],
            reply_markup=yes_or_no(user_id),
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
        reply_markup=get_add_another_node_or_done_keyboard(user_id),
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
            reply_markup=get_add_another_node_or_done_keyboard(user_id),
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
    if text in ADD_ANOTHER_NODE.values():
        user_data[user_id]["step"] = "add_another_node"
        keyboard = check_user_has_active_free_plan(user_id)
        bot.send_message(user_id, SELECT_NODE_TYPE[lg], reply_markup=keyboard)

    elif text in DONE.values():
        bot.send_message(
            user_id,
            FINISHED_ADDING_NODES[lg],
            reply_markup=advanced_user_flow_keyboard(user_id),
        )
    else:
        bot.send_message(
            user_id,
            ADD_ANOTHER_OR_DONE_PROMPT[lg],
            reply_markup=get_add_another_node_or_done_keyboard(user_id),
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
    dtmf = Pathways.objects.get(pathway_id=pathway_id).dtmf

    if validate_mobile(phone_number):
        gate = pre_call_check(user_id, phone_number, call_type="single")
        if not gate["allowed"]:
            bot.send_message(
                user_id, gate["message"],
                reply_markup=insufficient_balance_markup(user_id),
            )
            return
        response, status = send_call_through_pathway(pathway_id, phone_number, user_id, caller_id=None)
        if status == 200:
            call_id = response["call_id"]
            bot.send_message(
                user_id,
                f"{CALL_QUEUED_SUCCESSFULLY[lg]}\n{CALL_ID[lg]} {call_id}",
                reply_markup=get_main_menu_keyboard(user_id),
            )
            if dtmf:
                user = TelegramUser.objects.get(user_id=user_id)
                DTMF_Inbox.objects.create(
                    user_id=user,
                    call_id=call_id,
                    call_number=phone_number,
                    pathway_id=pathway_id,
                )
            return
        bot.send_message(user_id, f"{PROCESSING_ERROR[lg]} {response}")
    else:
        bot.send_message(
            user_id, INVALID_PHONE_NUMBER[lg], reply_markup=get_force_reply()
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("language:"))
def handle_language_selection_onboarding(call):
    user_id = call.from_user.id
    selected_language = call.data.split(":")[1]

    try:
        user, created = TelegramUser.objects.get_or_create(
            user_id=user_id, defaults={"user_name": str(user_id)}
        )
        user.language = selected_language
        user.save()

        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]["language"] = selected_language
        user_data[user_id]["step"] = "get_user_information"
        user_data[user_id]["set_language"] = selected_language

        signup(call.message)
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.send_message(user_id, f"Something went wrong. Please try /start again.")
        except Exception:
            pass


def handle_terms_and_conditions(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    markup = InlineKeyboardMarkup()
    # url = f"{webhook_url}/terms-and-conditions/"
    url = "https://www.termsfeed.com/blog/sample-terms-and-conditions-template/"
    web_app_info = types.WebAppInfo(url)
    view_terms_button = types.InlineKeyboardButton(
        VIEW_TERMS_AND_CONDITIONS_BUTTON[lg], web_app=web_app_info
    )
    accept_button = InlineKeyboardButton(ACCEPT[lg], callback_data="accept_terms")
    decline_terms = InlineKeyboardButton(DECLINE[lg], callback_data="decline_terms")
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
        # New onboarding: show quick start guide instead of forcing plan selection
        quick_start = (
            f"🚀 *{QUICK_START_TITLE[lg]}*\n\n"
            f"1️⃣ {QUICK_START_STEP_1[lg]}\n"
            f"2️⃣ {QUICK_START_STEP_2[lg]}\n"
            f"3️⃣ {QUICK_START_STEP_3[lg]}\n"
            f"4️⃣ {QUICK_START_STEP_4[lg]}"
        )
        from bot.keyboard_menus import get_onboarding_keyboard
        bot.send_message(
            user_id, quick_start,
            reply_markup=get_onboarding_keyboard(user_id),
            parse_mode="Markdown",
        )

    elif call.data == "decline_terms":
        markup = types.InlineKeyboardMarkup()
        view_terms_button = types.InlineKeyboardButton(
            VIEW_TERMS_AGAIN_BUTTON[lg], callback_data="view_terms_new"
        )
        exit_button = types.InlineKeyboardButton(
            EXIT_SETUP[lg], callback_data="exit_setup"
        )

        markup.add(view_terms_button, exit_button)
        msg = f"⚠️ {ACCEPT_TERMS_AND_CONDITIONS[lg]}"
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
        VIEW_TERMS_AND_CONDITIONS_BUTTON[lg], callback_data="view_terms_new"
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
        user_id, MAIN_MENU_PROMPT[lg], reply_markup=get_main_menu_keyboard(user_id)
    )


@bot.message_handler(func=lambda message: message.text in CALL_STATUS.values())
def handle_call_status(message):
    print("call status")
    user_id = message.chat.id
    lg = get_user_language(user_id)
    call_numbers = (
        CallLogsTable.objects.filter(user_id=user_id)
        .values_list("call_number", flat=True)
        .distinct()
    )
    print(call_numbers)

    if not call_numbers:
        bot.send_message(user_id, CALL_LOGS_NOT_FOUND[lg])
        return

    markup = types.InlineKeyboardMarkup()
    print("adding markup")
    for number in call_numbers:
        button_text = f"Phone: {number}"
        markup.add(
            types.InlineKeyboardButton(button_text, callback_data=f"status_{number}")
        )
    markup.add(types.InlineKeyboardButton(BACK[lg], callback_data="back_ivr_call"))

    bot.send_message(user_id, SELECT_PHONE_NUMBER_INBOX[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
def handle_phone_selection_for_status(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    phone_number = call.data.split("_")[1]
    user_data[user_id]["previous_number"] = phone_number

    call_logs = CallLogsTable.objects.filter(user_id=user_id, call_number=phone_number)
    markup = types.InlineKeyboardMarkup()
    for log in call_logs:
        button_text = f"Call ID: {log.call_id}"
        callback_data = f"statusCallId_{log.call_id}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    back_btn = types.InlineKeyboardButton(
        BACK[lg], callback_data="back_to_handle_call_status"
    )
    markup.add(back_btn)
    bot.send_message(user_id, SELECT_CALL_ID[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_handle_call_status")
def back_to_handle_call_status(call):
    handle_call_status(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("statusCallId_"))
def handle_status_call(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    call_id = call.data.split("_")[1]
    status = get_call_status(call_id)
    phone_number = user_data[user_id]["previous_number"]
    callback = f"status_{phone_number}"
    markup = InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton(BACK[lg], callback_data=callback)
    markup.add(back_btn)
    match status:
        case "new":
            bot.send_message(user_id, CALL_INITIATED[lg], reply_markup=markup)
        case "queued":
            bot.send_message(user_id, CALL_PREPARING[lg], reply_markup=markup)
        case "allocated":
            bot.send_message(user_id, CALL_RINGING[lg], reply_markup=markup)
        case "started":
            bot.send_message(user_id, CALL_ONGOING[lg], reply_markup=markup)
        case "complete":
            bot.send_message(user_id, CALL_COMPLETED[lg], reply_markup=markup)
        case _:
            bot.send_message(user_id, f"{error[lg]} {status}", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in AI_ASSISTED_FLOW.values())
def initiate_ai_assisted_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "get_task_name"
    bot.send_message(user_id, ASK_TASK_NAME[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_task_name"
)
def get_task_description(message):
    user_id = message.chat.id
    task_name = message.text
    if AI_Assisted_Tasks.objects.filter(task_name=task_name).exists():
        bot.send_message(user_id, f"{TASK_NAME_EXISTS[lg]}")
        return
    user_data[user_id]["task_name"] = task_name
    user_data[user_id]["step"] = "task_description"
    lg = get_user_language(user_id)
    bot.send_message(user_id, ASK_TASK_DESCRIPTION[lg], reply_markup=get_force_reply())


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "task_description"
)
def task_creation(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    task_description = message.text
    task_name = user_data[user_id]["task_name"]
    try:
        AI_Assisted_Tasks.objects.create(
            user_id=user_id,
            task_name=task_name,
            task_description=task_description,
        )
        bot.send_message(
            user_id, TASK_CREATED[lg], reply_markup=advanced_user_flow_keyboard(user_id)
        )
        user_data[user_id]["step"] = ""
        return
    except Exception:
        bot.send_message(
            user_id,
            PROCESSING_ERROR_MESSAGE[lg],
            reply_markup=advanced_user_flow_keyboard(user_id),
        )


@bot.message_handler(func=lambda message: message.text in AI_MADE_TASKS.values())
def view_ai_assisted_tasks(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    tasks = AI_Assisted_Tasks.objects.filter(user_id=user_id).values_list(
        "task_name", flat=True
    )
    markup = types.InlineKeyboardMarkup()
    for task in tasks:
        markup.add(types.InlineKeyboardButton(task, callback_data=f"viewtask_{task}"))

    bot.send_message(user_id, DISPLAY_IVR_FLOWS[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("viewtask_"))
def handle_call_back_view_task(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    task_name = call.data.split("_")[1]
    if user_id not in user_data:
        user_data[user_id] = {}
    task = AI_Assisted_Tasks.objects.get(
        user_id=user_id, task_name=task_name
    ).task_description
    user_data[user_id]["task"] = task
    call_type = user_data[user_id]["call_type"]
    if call_type == "single_ivr":
        user_data[user_id]["step"] = "get_single_call_recipient"
        bot.send_message(
            user_id, SINGLE_IVR_RECIPIENT_PROMPT[lg], reply_markup=get_force_reply()
        )

    else:
        user_data[user_id]["step"] = "campaign_name"
        bot.send_message(
            user_id, CAMPAIGN_NAME_PROMPT[lg], reply_markup=get_force_reply()
        )

    return


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "campaign_name"
)
def get_campaign_name(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user = TelegramUser.objects.get(user_id=user_id)
    user_data[user_id]["campaign_name"] = message.text
    campaign = CampaignLogs.objects.create(
        user_id=user,
        campaign_name=user_data[user_id]["campaign_name"],
        start_date=datetime.now(),
    )
    user_data[user_id]["campaign_id"] = campaign.campaign_id
    user_data[user_id]["step"] = "get_bulk_call_recipient"
    bot.send_message(
        user_id, BULK_IVR_RECIPIENT_PROMPT[lg], reply_markup=get_force_reply()
    )


def send_caller_id_selection_prompt(user_id):
    lg = get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()

    # Show user's own purchased numbers first (Private)
    user_numbers = UserPhoneNumber.objects.filter(
        user__user_id=user_id, is_active=True
    ).values_list("phone_number", flat=True)

    has_private = False
    if user_numbers:
        has_private = True
        for num in user_numbers:
            markup.add(
                types.InlineKeyboardButton(
                    f"🔒 {num} (Private)", callback_data=f"callerid_{num}"
                )
            )

    # Show admin shared numbers — available to all users
    admin_users = TelegramUser.objects.filter(is_admin=True).values_list("user_id", flat=True)
    admin_numbers = []
    if admin_users:
        admin_numbers = list(
            UserPhoneNumber.objects.filter(
                user__user_id__in=admin_users, is_active=True
            ).exclude(user__user_id=user_id)  # Don't duplicate if admin is the current user
            .values_list("phone_number", flat=True)
        )

    if admin_numbers:
        for num in admin_numbers:
            markup.add(
                types.InlineKeyboardButton(
                    f"🌐 {num} (Shared)", callback_data=f"callerid_{num}"
                )
            )

    random_caller_id_btn = types.InlineKeyboardButton(
        RANDOM_CALLER_ID[lg], callback_data="callerid_random"
    )
    markup.add(random_caller_id_btn)

    # Validate CallerIds against Retell — only show numbers that actually exist
    caller_ids = CallerIds.objects.all().values_list("caller_id", flat=True)
    if caller_ids:
        try:
            retell_numbers = get_retell_phone_number_set()
        except Exception:
            retell_numbers = None  # Fallback: show all if Retell API fails

        for caller_id in caller_ids:
            # Skip numbers not in Retell (if we could fetch the list)
            if retell_numbers is not None and caller_id not in retell_numbers:
                continue
            # Skip if already shown as admin or user number
            if caller_id in list(user_numbers) + admin_numbers:
                continue
            markup.add(
                types.InlineKeyboardButton(
                    caller_id, callback_data=f"callerid_{caller_id}"
                )
            )

    # Phone number management buttons
    markup.add(types.InlineKeyboardButton(BUY_NUMBER[lg], callback_data="buy_number"))
    if user_numbers:
        markup.add(types.InlineKeyboardButton(
            "📋 My Numbers", callback_data="my_numbers"
        ))

    # Education tip: nudge users toward private numbers
    tip = ""
    if admin_numbers and not has_private:
        tip = (
            "\n\n💡 *Tip:* Shared numbers work, but a *private number* "
            "gives you better answer rates and a dedicated caller identity. "
            "Tap *Buy Number* below to get your own!"
        )
    elif admin_numbers and has_private:
        tip = (
            "\n\n💡 *Tip:* Your private numbers give better answer rates "
            "than shared ones. We recommend using your own number."
        )

    bot.send_message(
        user_id,
        f"{CALLER_ID_SELECTION_PROMPT[lg]}{tip}",
        reply_markup=markup,
        parse_mode="Markdown",
    )


def get_summary_details():
    pass


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_bulk_call_recipient",
    content_types=["text", "document"],
)
def get_bulk_call_recipient(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    user_id = message.chat.id
    lg = get_user_language(user_id)
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
        print(f"Base Prompts: {base_prompts}")

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
            print(f"Base Prompts: {base_prompts}")

        except Exception as e:
            bot.send_message(
                user_id,
                f"{PROCESSING_ERROR[lg]} {str(e)}",
                reply_markup=get_main_menu_keyboard(user_id),
            )

            return
    calls_sent = len(base_prompts)

    if calls_sent > max_contacts:
        bot.send_message(
            user_id,
            f"{max_contacts}{REDUCE_NUMBER_OF_CONTACTS[lg]}"
            f"{ALLOWED_CONTACTS_PROMPT[lg]}",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return
    user_data[user_id]["call_count"] = calls_sent
    for number in base_prompts:
        check_validation = validate_mobile(number)
        if not check_validation:
            bot.send_message(user_id, INVALID_NUMBER_PROMPT[lg])
            return

    formatted_prompts = [{"phone_number": phone} for phone in base_prompts if phone]
    print(formatted_prompts)
    user_data[user_id]["base_prompts"] = formatted_prompts
    user_data[user_id]["phone_number"] = formatted_prompts
    user_data[user_id]["step"] = ""

    send_caller_id_selection_prompt(user_id)
    return


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "get_single_call_recipient"
)
def get_recipient_single_ivr(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    phone_number = message.text
    if not validate_mobile(phone_number):
        bot.send_message(
            user_id,
            "☎️ Please enter recipient's phone number in the right format"
            " (e.g., +14155552671). ",
        )
        return
    user_data[user_id]["step"] = ""
    if check_user_data(user_data, user_id) == "task":
        task = user_data[user_id]["task"]
    else:
        task = user_data[user_id]["pathway_id"]
    print(task)
    user_data[user_id]["phone_number"] = phone_number
    send_caller_id_selection_prompt(user_id)

    return


@bot.callback_query_handler(func=lambda call: call.data.startswith("callerid_"))
def handle_caller_id(call):
    print("caller id")
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    caller = call.data.replace("callerid_", "", 1)
    if caller == "random":
        caller_id = None
        caller = RANDOM_CALLER_ID[lg]
    else:
        caller_id = caller

    user_data[user_id]["caller_id"] = caller_id
    phone_number = user_data[user_id]["phone_number"]
    if check_user_data(user_data, user_id) == "task":
        task = user_data[user_id]["task"]
    else:
        pathway_id = user_data[user_id]["pathway_id"]
        task = Pathways.objects.get(pathway_id=pathway_id).pathway_name

    summary_details = f"{TASK[lg]} {task}\n\n" f"{CALLER_ID[lg]} {caller}\n"

    # Initialize recording preference
    if "recording_requested" not in user_data[user_id]:
        user_data[user_id]["recording_requested"] = False

    if user_data[user_id]["call_type"] == "bulk_ivr":
        total_count = user_data[user_id]["call_count"]
        summary_details += f"{RECIPIENTS[lg]}\n"
        for number in phone_number:
            summary_details += f"{number['phone_number']}\n"
        summary_details += (
            f"{CAMPAIGN[lg]} {user_data[user_id]['campaign_name']}\n\n"
            f"{TOTAL_NUMBERS_BULK[lg]} {total_count}\n"
        )
        rec_cost = f"${0.02 * total_count:.2f}"
        summary_details += f"\n🎙 Recording: {'ON' if user_data[user_id]['recording_requested'] else 'OFF'} ({rec_cost} total)\n"
    else:
        summary_details += f"{RECIPIENTS[lg]} {phone_number}\n"
        summary_details += f"\n🎙 Recording: {'ON' if user_data[user_id]['recording_requested'] else 'OFF'} ($0.02/call)\n"

    summary_details += f"\n{PROCEED[lg]}"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(YES_PROCEED[lg]))
    rec_label = "🔴 Recording: ON ($0.02)" if user_data[user_id]["recording_requested"] else "⚪ Recording: OFF (tap to enable $0.02)"
    markup.add(types.KeyboardButton(rec_label))
    markup.add(types.KeyboardButton(EDIT_DETAILS[lg]))
    bot.send_message(user_id, summary_details, reply_markup=markup)



# =============================================================================
# Phone Number Purchase & Management
# =============================================================================

PHONE_NUMBER_MONTHLY_COST_LOCAL = 2.00
PHONE_NUMBER_MONTHLY_COST_TOLL_FREE = 5.00


@bot.callback_query_handler(func=lambda call: call.data == "buy_number")
def handle_buy_number(call):
    """Show phone number purchase options."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"📞 US Local Number (${PHONE_NUMBER_MONTHLY_COST_LOCAL:.0f}/mo)",
        callback_data="buynum_US_local"
    ))
    markup.add(types.InlineKeyboardButton(
        f"📞 US Toll-Free Number (${PHONE_NUMBER_MONTHLY_COST_TOLL_FREE:.0f}/mo)",
        callback_data="buynum_US_tollfree"
    ))
    markup.add(types.InlineKeyboardButton(
        f"📞 Canada Local Number (${PHONE_NUMBER_MONTHLY_COST_LOCAL:.0f}/mo)",
        callback_data="buynum_CA_local"
    ))
    markup.add(types.InlineKeyboardButton(
        "⬅️ Back", callback_data="buynum_back"
    ))

    bot.send_message(
        user_id,
        "🛒 *Purchase a Dedicated Phone Number*\n\n"
        "Get your own caller ID for outbound calls.\n"
        "Your number will be exclusively assigned to you.\n\n"
        "Choose number type:",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("buynum_"))
def handle_buynum_selection(call):
    """Handle number type selection and prompt for area code."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    data = call.data.replace("buynum_", "")

    if data == "back":
        send_caller_id_selection_prompt(user_id)
        return

    # Parse: US_local, US_tollfree, CA_local
    parts = data.split("_")
    country = parts[0]  # US or CA
    num_type = parts[1]  # local or tollfree

    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["buy_number_country"] = country
    user_data[user_id]["buy_number_type"] = num_type
    user_data[user_id]["buy_number_toll_free"] = (num_type == "tollfree")
    user_data[user_id]["buy_number_cost"] = (
        PHONE_NUMBER_MONTHLY_COST_TOLL_FREE if num_type == "tollfree"
        else PHONE_NUMBER_MONTHLY_COST_LOCAL
    )
    user_data[user_id]["step"] = "buy_number_area_code"

    if num_type == "tollfree":
        # No area code needed for toll-free
        handle_buy_number_confirm(user_id, area_code=None)
    else:
        bot.send_message(
            user_id,
            f"Enter preferred area code for your {country} number "
            f"(e.g., 415 for San Francisco, 212 for New York).\n\n"
            f"Send 'any' for a random area code:",
            reply_markup=get_force_reply(),
        )


@bot.message_handler(
    func=lambda message: user_data.get(message.chat.id, {}).get("step")
    == "buy_number_area_code"
)
def handle_area_code_input(message):
    """Process area code and show payment options."""
    user_id = message.chat.id
    text = message.text.strip().lower()

    area_code = None
    if text != "any":
        try:
            area_code = int(text)
            if area_code < 100 or area_code > 999:
                bot.send_message(user_id, "Please enter a valid 3-digit area code or 'any':")
                return
        except ValueError:
            bot.send_message(user_id, "Please enter a valid 3-digit area code or 'any':")
            return

    handle_buy_number_confirm(user_id, area_code)


def handle_buy_number_confirm(user_id, area_code):
    """Show payment confirmation for phone number purchase."""
    lg = get_user_language(user_id)
    cost = user_data[user_id]["buy_number_cost"]
    country = user_data[user_id]["buy_number_country"]
    num_type = user_data[user_id]["buy_number_type"]
    user_data[user_id]["buy_number_area_code"] = area_code
    user_data[user_id]["step"] = None

    # Get wallet balance
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        balance = float(user.wallet_balance)
    except TelegramUser.DoesNotExist:
        balance = 0

    area_text = f"Area code: {area_code}" if area_code else "Random area code"
    type_text = "Toll-Free" if num_type == "tollfree" else "Local"

    markup = types.InlineKeyboardMarkup()
    # Wallet payment option
    if balance >= cost:
        markup.add(types.InlineKeyboardButton(
            f"💰 Pay from Wallet (${balance:.2f})",
            callback_data="buynum_pay_wallet"
        ))
    else:
        markup.add(types.InlineKeyboardButton(
            f"💰 Wallet (${balance:.2f}) — Insufficient",
            callback_data="buynum_pay_insufficient"
        ))
    # Crypto payment option
    markup.add(types.InlineKeyboardButton(
        "💎 Pay with Crypto",
        callback_data="buynum_pay_crypto"
    ))
    markup.add(types.InlineKeyboardButton(
        "⬅️ Cancel", callback_data="buynum_back"
    ))

    bot.send_message(
        user_id,
        f"📋 *Phone Number Purchase Summary*\n\n"
        f"Type: {country} {type_text}\n"
        f"{area_text}\n"
        f"Monthly cost: ${cost:.2f}/month\n"
        f"Auto-renewal: Yes (from wallet)\n\n"
        f"Choose payment method:",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data == "buynum_pay_insufficient")
def handle_buynum_insufficient(call):
    user_id = call.message.chat.id
    bot.send_message(
        user_id,
        "Insufficient wallet balance. Please top up first.",
        reply_markup=insufficient_balance_markup(user_id),
    )


@bot.callback_query_handler(func=lambda call: call.data == "buynum_pay_wallet")
def handle_buynum_pay_wallet(call):
    """Process phone number purchase via wallet."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    cost = user_data.get(user_id, {}).get("buy_number_cost", PHONE_NUMBER_MONTHLY_COST_LOCAL)
    country = user_data.get(user_id, {}).get("buy_number_country", "US")
    toll_free = user_data.get(user_id, {}).get("buy_number_toll_free", False)
    area_code = user_data.get(user_id, {}).get("buy_number_area_code")

    bot.send_message(user_id, "⏳ Purchasing your phone number... Please wait.")

    # Debit wallet first
    result = debit_wallet(
        user_id, cost,
        description=f"Phone number purchase ({country})",
        tx_type="SUB",
    )
    if result["status"] != 200:
        bot.send_message(
            user_id,
            f"Payment failed: {result['message']}",
            reply_markup=insufficient_balance_markup(user_id),
        )
        return

    # Purchase from Retell
    nickname = f"user_{user_id}"
    retell_result = purchase_phone_number(
        area_code=area_code,
        country_code=country,
        toll_free=toll_free,
        nickname=nickname,
    )

    if not retell_result:
        # Refund wallet
        from payment.views import refund_wallet
        refund_wallet(user_id, cost, description="Phone number purchase failed — refund")
        bot.send_message(
            user_id,
            "Failed to purchase number from provider. Wallet has been refunded.\n"
            "Please try again or contact support.",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return

    # Save to database
    from django.utils import timezone as tz
    from dateutil.relativedelta import relativedelta

    now = tz.now()
    user_obj = TelegramUser.objects.get(user_id=user_id)
    phone_record = UserPhoneNumber.objects.create(
        user=user_obj,
        phone_number=retell_result.phone_number,
        country_code=country,
        area_code=area_code,
        is_toll_free=toll_free,
        nickname=nickname,
        monthly_cost=cost,
        next_renewal_date=now + relativedelta(months=1),
        is_active=True,
        auto_renew=True,
    )

    # Bind agent to the purchased number for outbound use
    try:
        from bot.models import Pathways
        user_pathway = Pathways.objects.filter(user_id=user_obj).first()
        if user_pathway:
            update_phone_number_agent(
                retell_result.phone_number,
                outbound_agent_id=user_pathway.pathway_id,
                nickname=nickname,
            )
            logger.info(f"Bound agent {user_pathway.pathway_id} to {retell_result.phone_number}")
    except Exception as e:
        logger.warning(f"Agent binding skipped for {retell_result.phone_number}: {e}")

    bot.send_message(
        user_id,
        f"✅ *Phone Number Purchased!*\n\n"
        f"📞 Your number: `{retell_result.phone_number}`\n"
        f"🌍 Country: {country}\n"
        f"💰 Cost: ${cost:.2f}/month (auto-renew from wallet)\n"
        f"📅 Next renewal: {phone_record.next_renewal_date.strftime('%Y-%m-%d')}\n\n"
        f"This number will now appear in your caller ID selection.\n"
        f"Use 📋 My Numbers to manage agent binding for inbound calls.",
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data == "buynum_pay_crypto")
def handle_buynum_pay_crypto(call):
    """Process phone number purchase via crypto."""
    user_id = call.message.chat.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["transaction_type"] = "buy_number"
    user_data[user_id]["amount"] = user_data[user_id].get(
        "buy_number_cost", PHONE_NUMBER_MONTHLY_COST_LOCAL
    )
    currency_selection(user_id)


@bot.callback_query_handler(func=lambda call: call.data == "my_numbers")
def handle_my_numbers(call):
    """Show user's purchased phone numbers with management options."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    numbers = UserPhoneNumber.objects.filter(
        user__user_id=user_id, is_active=True
    )

    if not numbers.exists():
        bot.send_message(
            user_id,
            "You don't have any phone numbers yet.\n"
            "Use 'Buy Number' to get your own dedicated caller ID.",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return

    markup = types.InlineKeyboardMarkup()
    msg = "📋 *Your Phone Numbers*\n\n"

    for num in numbers:
        renew_date = num.next_renewal_date.strftime("%Y-%m-%d")
        vm_icon = "📬" if num.voicemail_enabled else ""
        fwd_icon = f"→ {num.forwarding_number}" if num.forwarding_enabled and num.forwarding_number else ""
        msg += (
            f"📞 `{num.phone_number}`\n"
            f"   💰 ${num.monthly_cost}/mo | Renews: {renew_date}\n"
            f"   Auto-renew: {'✅' if num.auto_renew else '❌'}"
            f"{' | ' + vm_icon + ' VM' if vm_icon else ''}"
            f"{' | ' + fwd_icon if fwd_icon else ''}\n\n"
        )
        markup.add(types.InlineKeyboardButton(
            f"⚙️ Settings {num.phone_number[-4:]}",
            callback_data=f"numset_{num.phone_number}"
        ))
        markup.add(types.InlineKeyboardButton(
            f"🔗 Set Inbound Script {num.phone_number[-4:]}",
            callback_data=f"bindagent_{num.phone_number}"
        ))
        markup.add(types.InlineKeyboardButton(
            f"🗑 Release {num.phone_number}",
            callback_data=f"releasenum_{num.phone_number}"
        ))
        if num.auto_renew:
            markup.add(types.InlineKeyboardButton(
                f"🔕 Disable auto-renew {num.phone_number[-4:]}",
                callback_data=f"togglerenew_{num.phone_number}"
            ))
        else:
            markup.add(types.InlineKeyboardButton(
                f"🔔 Enable auto-renew {num.phone_number[-4:]}",
                callback_data=f"togglerenew_{num.phone_number}"
            ))

    # SMS Inbox button
    unread_sms = SMSInbox.objects.filter(user__user_id=user_id, is_read=False).count()
    sms_label = f"📩 SMS Inbox ({unread_sms} unread)" if unread_sms else "📩 SMS Inbox"
    markup.add(types.InlineKeyboardButton(sms_label, callback_data="sms_inbox"))

    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="buynum_back"))
    bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("releasenum_"))
def handle_release_number(call):
    """Release a purchased phone number."""
    user_id = call.message.chat.id
    phone = call.data.replace("releasenum_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()

    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "✅ Yes, release it", callback_data=f"confirmrelease_{phone}"
    ))
    markup.add(types.InlineKeyboardButton(
        "❌ Cancel", callback_data="my_numbers"
    ))

    bot.send_message(
        user_id,
        f"⚠️ Are you sure you want to release `{phone}`?\n\n"
        f"This action cannot be undone. The number will be returned to the provider.",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirmrelease_"))
def handle_confirm_release(call):
    """Confirm and execute phone number release."""
    user_id = call.message.chat.id
    phone = call.data.replace("confirmrelease_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()

    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    # Release from Retell
    success = release_phone_number(phone)
    if success:
        record.is_active = False
        record.save()
        bot.send_message(
            user_id,
            f"✅ Number `{phone}` has been released.",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        bot.send_message(
            user_id,
            "Failed to release number. Please try again or contact support.",
            reply_markup=get_main_menu_keyboard(user_id),
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("togglerenew_"))
def handle_toggle_auto_renew(call):
    """Toggle auto-renewal for a phone number."""
    user_id = call.message.chat.id
    phone = call.data.replace("togglerenew_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()

    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    record.auto_renew = not record.auto_renew
    record.save()

    status = "enabled" if record.auto_renew else "disabled"
    bot.send_message(
        user_id,
        f"Auto-renewal {status} for `{phone}`.",
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("bindagent_"))
def handle_bind_agent_prompt(call):
    """Show available agents/flows for binding to a phone number."""
    user_id = call.message.chat.id
    phone = call.data.replace("bindagent_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    # Get user's pathways/agents
    user_obj = TelegramUser.objects.get(user_id=user_id)
    pathways = Pathways.objects.filter(user_id=user_obj)

    markup = types.InlineKeyboardMarkup()
    if pathways.exists():
        for pw in pathways:
            markup.add(types.InlineKeyboardButton(
                f"🤖 {pw.pathway_name}",
                callback_data=f"setbind_{phone}_{pw.pathway_id}"
            ))
    else:
        bot.send_message(
            user_id,
            "You don't have any call scripts yet. Create a script first, then assign it to your number.",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return

    # Option to unbind
    markup.add(types.InlineKeyboardButton(
        "🚫 Remove inbound script", callback_data=f"setbind_{phone}_none"
    ))
    markup.add(types.InlineKeyboardButton("Back", callback_data="my_numbers"))

    bot.send_message(
        user_id,
        f"📞 *Set Inbound Script for* `{phone}`\n\n"
        f"Choose a call script to handle *incoming calls* to this number.\n"
        f"When someone calls you, the AI will follow this script automatically.",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("setbind_"))
def handle_set_bind_agent(call):
    """Execute agent binding for a phone number."""
    user_id = call.message.chat.id
    parts = call.data.split("_", 2)  # setbind, phone, agent_id
    if len(parts) < 3:
        bot.send_message(user_id, "Invalid selection.", reply_markup=get_main_menu_keyboard(user_id))
        return

    phone = parts[1]
    agent_id = parts[2]

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    if agent_id == "none":
        result = update_phone_number_agent(phone, inbound_agent_id="null")
        if result:
            bot.send_message(
                user_id,
                f"Inbound script removed from `{phone}`. Incoming calls will no longer be answered by AI.",
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                user_id,
                "Failed to update. Please try again.",
                reply_markup=get_main_menu_keyboard(user_id),
            )
        return

    # Bind both inbound and outbound
    result = update_phone_number_agent(
        phone,
        inbound_agent_id=agent_id,
        outbound_agent_id=agent_id,
    )
    if result:
        try:
            pw_name = Pathways.objects.get(pathway_id=agent_id).pathway_name
        except Pathways.DoesNotExist:
            pw_name = agent_id
        bot.send_message(
            user_id,
            f"*{pw_name}* is now set as the inbound script for `{phone}`.\n\n"
            f"Incoming calls to this number will be handled by this script automatically.",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        bot.send_message(
            user_id,
            "Failed to bind agent. Please try again or contact support.",
            reply_markup=get_main_menu_keyboard(user_id),
        )


# =============================================================================
# DTMF Supervisor Approve/Reject Handlers (single calls only)
# =============================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith("dtmf_approve_"))
def handle_dtmf_approve(call):
    """Bot user approves the DTMF input — proceed with the call flow."""
    user_id = call.message.chat.id
    approval_id = call.data.replace("dtmf_approve_", "")
    try:
        from django.utils import timezone as tz
        approval = PendingDTMFApproval.objects.get(id=int(approval_id), user_id=user_id)
        if approval.status == "pending":
            approval.status = "approved"
            approval.resolved_at = tz.now()
            approval.save()
            bot.edit_message_text(
                f"✅ *Approved* — digits `{approval.digits}` accepted.\nCall proceeding.",
                chat_id=user_id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
            )
        else:
            bot.answer_callback_query(call.id, f"Already {approval.status}.")
    except PendingDTMFApproval.DoesNotExist:
        bot.answer_callback_query(call.id, "Approval not found.")
    except Exception as e:
        logger.error(f"[dtmf_approve] Error: {e}")
        bot.answer_callback_query(call.id, "Error processing approval.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dtmf_reject_"))
def handle_dtmf_reject(call):
    """Bot user rejects the DTMF input — ask caller to re-enter."""
    user_id = call.message.chat.id
    approval_id = call.data.replace("dtmf_reject_", "")
    try:
        from django.utils import timezone as tz
        approval = PendingDTMFApproval.objects.get(id=int(approval_id), user_id=user_id)
        if approval.status == "pending":
            approval.status = "rejected"
            approval.resolved_at = tz.now()
            approval.save()
            bot.edit_message_text(
                f"❌ *Rejected* — digits `{approval.digits}` declined.\nAgent will ask caller to re-enter.",
                chat_id=user_id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
            )
        else:
            bot.answer_callback_query(call.id, f"Already {approval.status}.")
    except PendingDTMFApproval.DoesNotExist:
        bot.answer_callback_query(call.id, "Approval not found.")
    except Exception as e:
        logger.error(f"[dtmf_reject] Error: {e}")
        bot.answer_callback_query(call.id, "Error processing rejection.")


# =============================================================================
# SMS Inbox Handlers
# =============================================================================

@bot.callback_query_handler(func=lambda call: call.data == "sms_inbox")
def handle_sms_inbox(call):
    """Show SMS inbox for the user."""
    user_id = call.message.chat.id
    lg = get_user_language(user_id)

    messages = SMSInbox.objects.filter(user__user_id=user_id).order_by("-received_at")[:20]

    if not messages.exists():
        bot.send_message(
            user_id,
            "📭 No SMS messages in your inbox.",
            reply_markup=get_main_menu_keyboard(user_id),
        )
        return

    markup = types.InlineKeyboardMarkup()
    msg = "📩 *SMS Inbox* (latest 20)\n\n"
    for sms in messages:
        time_str = sms.received_at.strftime("%m/%d %H:%M")
        preview = sms.message[:40] + "..." if len(sms.message) > 40 else sms.message
        unread = "🔵" if not sms.is_read else "⚪"
        msg += f"{unread} `{sms.from_number}` → `{sms.phone_number}`\n"
        msg += f"   {time_str}: {preview}\n\n"
        markup.add(types.InlineKeyboardButton(
            f"📖 View {sms.from_number} ({time_str})",
            callback_data=f"sms_view_{sms.id}"
        ))

    markup.add(types.InlineKeyboardButton(
        "🗑 Clear All Read", callback_data="sms_clear_read"
    ))

    bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("sms_view_"))
def handle_sms_view(call):
    """View a single SMS message in full."""
    user_id = call.message.chat.id
    sms_id = call.data.replace("sms_view_", "")
    try:
        sms = SMSInbox.objects.get(id=int(sms_id), user__user_id=user_id)
        sms.is_read = True
        sms.save()
        bot.send_message(
            user_id,
            f"📩 *SMS Message*\n\n"
            f"From: `{sms.from_number}`\n"
            f"To: `{sms.phone_number}`\n"
            f"Time: {sms.received_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"Message:\n{sms.message}",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    except SMSInbox.DoesNotExist:
        bot.answer_callback_query(call.id, "Message not found.")
    except Exception as e:
        logger.error(f"[sms_view] Error: {e}")
        bot.answer_callback_query(call.id, "Error loading message.")


@bot.callback_query_handler(func=lambda call: call.data == "sms_clear_read")
def handle_sms_clear_read(call):
    """Clear all read SMS messages."""
    user_id = call.message.chat.id
    deleted_count = SMSInbox.objects.filter(user__user_id=user_id, is_read=True).delete()[0]
    bot.send_message(
        user_id,
        f"🗑 Cleared {deleted_count} read messages.",
        reply_markup=get_main_menu_keyboard(user_id),
    )


# =============================================================================
# Voicemail & Call Forwarding Settings
# =============================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith("numset_"))
def handle_number_settings(call):
    """Show settings for a purchased number (voicemail, forwarding)."""
    user_id = call.message.chat.id
    phone = call.data.replace("numset_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    markup = types.InlineKeyboardMarkup()

    # Voicemail toggle
    vm_status = "ON ✅" if record.voicemail_enabled else "OFF ❌"
    markup.add(types.InlineKeyboardButton(
        f"📬 Voicemail: {vm_status}",
        callback_data=f"vm_toggle_{phone}"
    ))
    if record.voicemail_enabled:
        markup.add(types.InlineKeyboardButton(
            "✏️ Edit Voicemail Message",
            callback_data=f"vm_edit_{phone}"
        ))

    # Call forwarding toggle
    fwd_status = f"ON → {record.forwarding_number}" if record.forwarding_enabled and record.forwarding_number else "OFF ❌"
    markup.add(types.InlineKeyboardButton(
        f"📞 Forwarding: {fwd_status}",
        callback_data=f"fwd_toggle_{phone}"
    ))
    if not record.forwarding_enabled:
        markup.add(types.InlineKeyboardButton(
            "📞 Set Forwarding Number",
            callback_data=f"fwd_set_{phone}"
        ))

    # Business hours toggle
    if record.business_hours_enabled and record.business_hours_start and record.business_hours_end:
        bh_status = f"ON ({record.business_hours_start.strftime('%H:%M')}-{record.business_hours_end.strftime('%H:%M')} {record.business_hours_timezone})"
    else:
        bh_status = "OFF ❌"
    markup.add(types.InlineKeyboardButton(
        f"🕐 Business Hours: {bh_status}",
        callback_data=f"bh_toggle_{phone}"
    ))
    if not record.business_hours_enabled:
        markup.add(types.InlineKeyboardButton(
            "🕐 Set Business Hours",
            callback_data=f"bh_set_{phone}"
        ))

    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="my_numbers"))

    bot.send_message(
        user_id,
        f"⚙️ *Settings for* `{phone}`\n\n"
        f"📬 Voicemail: {vm_status}\n"
        f"📞 Forwarding: {fwd_status}\n"
        f"🕐 Business Hours: {bh_status}",
        reply_markup=markup,
        parse_mode="Markdown",
    )


def _sync_inbound_settings_to_retell(user_id, phone_record):
    """Sync voicemail/forwarding/business hours settings to the Retell agent bound to this number."""
    try:
        user_obj = TelegramUser.objects.get(user_id=user_id)
        user_pathway = Pathways.objects.filter(user_id=user_obj).first()
        if user_pathway:
            update_agent_inbound_settings(user_pathway.pathway_id, phone_record)
            logger.info(f"Synced inbound settings to agent {user_pathway.pathway_id} for {phone_record.phone_number}")
    except Exception as e:
        logger.warning(f"Failed to sync inbound settings for user {user_id}: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("vm_toggle_"))
def handle_voicemail_toggle(call):
    """Toggle voicemail on/off for a purchased number."""
    user_id = call.message.chat.id
    phone = call.data.replace("vm_toggle_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    record.voicemail_enabled = not record.voicemail_enabled
    record.save()

    # Auto-update Retell agent prompt
    _sync_inbound_settings_to_retell(user_id, record)

    status = "enabled ✅" if record.voicemail_enabled else "disabled ❌"
    bot.send_message(
        user_id,
        f"📬 Voicemail {status} for `{phone}`.\n"
        + (f"Message: \"{record.voicemail_message[:80]}...\"" if record.voicemail_enabled else ""),
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("vm_edit_"))
def handle_voicemail_edit(call):
    """Prompt user to type a new voicemail message."""
    user_id = call.message.chat.id
    phone = call.data.replace("vm_edit_", "")

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "edit_voicemail"
    user_data[user_id]["edit_vm_phone"] = phone

    bot.send_message(
        user_id,
        f"✏️ Type your new voicemail greeting for `{phone}`.\n"
        f"This is what the AI agent will say to callers when voicemail is active.",
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("fwd_toggle_"))
def handle_forwarding_toggle(call):
    """Toggle call forwarding on/off for a purchased number."""
    user_id = call.message.chat.id
    phone = call.data.replace("fwd_toggle_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    if record.forwarding_enabled:
        record.forwarding_enabled = False
        record.save()
        _sync_inbound_settings_to_retell(user_id, record)
        bot.send_message(
            user_id,
            f"📞 Call forwarding disabled for `{phone}`.",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        if record.forwarding_number:
            record.forwarding_enabled = True
            record.save()
            _sync_inbound_settings_to_retell(user_id, record)
            bot.send_message(
                user_id,
                f"📞 Call forwarding enabled for `{phone}` → `{record.forwarding_number}`.",
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="Markdown",
            )
        else:
            # Need to set a number first
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]["step"] = "set_forwarding"
            user_data[user_id]["fwd_phone"] = phone
            bot.send_message(
                user_id,
                "📞 Enter the phone number to forward calls to (E.164 format, e.g., +14155551234):",
            )


@bot.callback_query_handler(func=lambda call: call.data.startswith("fwd_set_"))
def handle_forwarding_set(call):
    """Prompt user to enter a forwarding number."""
    user_id = call.message.chat.id
    phone = call.data.replace("fwd_set_", "")

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "set_forwarding"
    user_data[user_id]["fwd_phone"] = phone

    bot.send_message(
        user_id,
        "📞 Enter the phone number to forward calls to (E.164 format, e.g., +14155551234):",
    )


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get("step") == "edit_voicemail")
def handle_voicemail_message_input(message):
    """Save the new voicemail message."""
    user_id = message.chat.id
    phone = user_data[user_id].get("edit_vm_phone", "")
    new_message = message.text.strip()

    if not new_message:
        bot.send_message(user_id, "Message cannot be empty. Please try again.")
        return

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if record:
        record.voicemail_message = new_message
        record.save()
        _sync_inbound_settings_to_retell(user_id, record)
        bot.send_message(
            user_id,
            f"✅ Voicemail message updated for `{phone}`.\n\n"
            f"New message: \"{new_message[:100]}{'...' if len(new_message) > 100 else ''}\"",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))

    user_data[user_id].pop("step", None)
    user_data[user_id].pop("edit_vm_phone", None)


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get("step") == "set_forwarding")
def handle_forwarding_number_input(message):
    """Save the forwarding number."""
    user_id = message.chat.id
    phone = user_data[user_id].get("fwd_phone", "")
    fwd_number = message.text.strip()

    # Basic validation
    import re
    if not re.match(r"^\+?\d{10,15}$", fwd_number):
        bot.send_message(user_id, "Invalid format. Please enter a valid phone number (E.164, e.g., +14155551234).")
        return

    if not fwd_number.startswith("+"):
        fwd_number = "+" + fwd_number

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if record:
        record.forwarding_number = fwd_number
        record.forwarding_enabled = True
        record.save()
        _sync_inbound_settings_to_retell(user_id, record)
        bot.send_message(
            user_id,
            f"✅ Call forwarding set for `{phone}` → `{fwd_number}`.",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))

    user_data[user_id].pop("step", None)
    user_data[user_id].pop("fwd_phone", None)


@bot.callback_query_handler(func=lambda call: call.data.startswith("bh_toggle_"))
def handle_business_hours_toggle(call):
    """Toggle business hours on/off for a purchased number."""
    user_id = call.message.chat.id
    phone = call.data.replace("bh_toggle_", "")

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if not record:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))
        return

    if record.business_hours_enabled:
        record.business_hours_enabled = False
        record.save()
        _sync_inbound_settings_to_retell(user_id, record)
        bot.send_message(
            user_id,
            f"🕐 Business hours disabled for `{phone}`. Calls accepted 24/7.",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        if record.business_hours_start and record.business_hours_end:
            record.business_hours_enabled = True
            record.save()
            _sync_inbound_settings_to_retell(user_id, record)
            bot.send_message(
                user_id,
                f"🕐 Business hours enabled for `{phone}`.\n"
                f"Hours: {record.business_hours_start.strftime('%H:%M')}-{record.business_hours_end.strftime('%H:%M')} ({record.business_hours_timezone})",
                reply_markup=get_main_menu_keyboard(user_id),
                parse_mode="Markdown",
            )
        else:
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]["step"] = "set_business_hours"
            user_data[user_id]["bh_phone"] = phone
            bot.send_message(
                user_id,
                "🕐 Enter business hours in format: `HH:MM-HH:MM TIMEZONE`\n"
                "Example: `09:00-17:00 US/Eastern`\n\n"
                "Common timezones: US/Eastern, US/Central, US/Pacific, Europe/London, Asia/Tokyo",
                parse_mode="Markdown",
            )


@bot.callback_query_handler(func=lambda call: call.data.startswith("bh_set_"))
def handle_business_hours_set(call):
    """Prompt user to enter business hours."""
    user_id = call.message.chat.id
    phone = call.data.replace("bh_set_", "")

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "set_business_hours"
    user_data[user_id]["bh_phone"] = phone

    bot.send_message(
        user_id,
        "🕐 Enter business hours in format: `HH:MM-HH:MM TIMEZONE`\n"
        "Example: `09:00-17:00 US/Eastern`\n\n"
        "Common timezones: US/Eastern, US/Central, US/Pacific, Europe/London, Asia/Tokyo",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get("step") == "set_business_hours")
def handle_business_hours_input(message):
    """Parse and save business hours."""
    user_id = message.chat.id
    phone = user_data[user_id].get("bh_phone", "")
    text = message.text.strip()

    import re
    from datetime import time as dt_time

    # Parse: HH:MM-HH:MM TIMEZONE
    match = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s+(.+)$", text)
    if not match:
        bot.send_message(
            user_id,
            "Invalid format. Please use: `HH:MM-HH:MM TIMEZONE`\nExample: `09:00-17:00 US/Eastern`",
            parse_mode="Markdown",
        )
        return

    start_str, end_str, tz_str = match.groups()

    # Validate timezone
    import pytz
    try:
        pytz.timezone(tz_str.strip())
    except pytz.exceptions.UnknownTimeZoneError:
        bot.send_message(user_id, f"Unknown timezone: {tz_str}. Try US/Eastern, US/Pacific, Europe/London, etc.")
        return

    # Parse times
    try:
        start_parts = start_str.split(":")
        end_parts = end_str.split(":")
        start_time = dt_time(int(start_parts[0]), int(start_parts[1]))
        end_time = dt_time(int(end_parts[0]), int(end_parts[1]))
    except (ValueError, IndexError):
        bot.send_message(user_id, "Invalid time format. Use HH:MM (24-hour).")
        return

    record = UserPhoneNumber.objects.filter(
        user__user_id=user_id, phone_number=phone, is_active=True
    ).first()
    if record:
        record.business_hours_start = start_time
        record.business_hours_end = end_time
        record.business_hours_timezone = tz_str.strip()
        record.business_hours_enabled = True
        record.save()
        _sync_inbound_settings_to_retell(user_id, record)
        bot.send_message(
            user_id,
            f"✅ Business hours set for `{phone}`\n"
            f"🕐 {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({tz_str.strip()})\n\n"
            f"Outside these hours, callers will be routed to voicemail (if enabled).",
            reply_markup=get_main_menu_keyboard(user_id),
            parse_mode="Markdown",
        )
    else:
        bot.send_message(user_id, "Number not found.", reply_markup=get_main_menu_keyboard(user_id))

    user_data[user_id].pop("step", None)
    user_data[user_id].pop("bh_phone", None)


@bot.message_handler(func=lambda message: message.text and "Recording:" in message.text and ("tap to enable" in message.text or "ON ($0.02)" in message.text))
def handle_recording_toggle(message):
    """Toggle recording on/off in the call confirmation screen."""
    user_id = message.chat.id
    lg = get_user_language(user_id)

    if user_id not in user_data:
        return

    # Toggle recording preference
    current = user_data[user_id].get("recording_requested", False)
    user_data[user_id]["recording_requested"] = not current

    # Check wallet balance if enabling recording
    if not current:  # turning ON
        from payment.views import check_user_balance
        wallet = check_user_balance(user_id)
        balance = float(wallet.get("data", {}).get("amount", 0))
        call_type = user_data[user_id].get("call_type", "single_ivr")
        if call_type == "bulk_ivr":
            total_count = user_data[user_id].get("call_count", 1)
            rec_cost = 0.02 * total_count
        else:
            rec_cost = 0.02

        if balance < rec_cost:
            user_data[user_id]["recording_requested"] = False
            bot.send_message(
                user_id,
                f"Insufficient balance for recording. Need ${rec_cost:.2f}, have ${balance:.2f}.\n"
                f"Top up your wallet to enable recording.",
            )

    # Re-show the confirmation with updated toggle
    # Rebuild summary
    caller_id = user_data[user_id].get("caller_id")
    phone_number = user_data[user_id].get("phone_number")
    caller = caller_id if caller_id else "Random"

    if user_data[user_id].get("call_type") == "single_ivr":
        if "task" in user_data[user_id]:
            task_name = user_data[user_id]["task"]
        elif "pathway_id" in user_data[user_id]:
            try:
                task_name = Pathways.objects.get(pathway_id=user_data[user_id]["pathway_id"]).pathway_name
            except Exception:
                task_name = "Call"
        else:
            task_name = "Call"

        rec_status = "ON" if user_data[user_id]["recording_requested"] else "OFF"
        summary = (
            f"Task: {task_name}\n\n"
            f"Caller ID: {caller}\n"
            f"Recipient: {phone_number}\n\n"
            f"🎙 Recording: {rec_status} ($0.02/call)\n\n"
            f"Proceed?"
        )
    else:
        total_count = user_data[user_id].get("call_count", 0)
        rec_cost = f"${0.02 * total_count:.2f}"
        rec_status = "ON" if user_data[user_id]["recording_requested"] else "OFF"
        campaign_name = user_data[user_id].get("campaign_name", "Campaign")

        if "task" in user_data[user_id]:
            task_name = user_data[user_id]["task"]
        elif "pathway_id" in user_data[user_id]:
            try:
                task_name = Pathways.objects.get(pathway_id=user_data[user_id]["pathway_id"]).pathway_name
            except Exception:
                task_name = "Call"
        else:
            task_name = "Call"

        summary = (
            f"Task: {task_name}\n\n"
            f"Caller ID: {caller}\n"
            f"Campaign: {campaign_name}\n"
            f"Total Numbers: {total_count}\n\n"
            f"🎙 Recording: {rec_status} ({rec_cost} total)\n\n"
            f"Proceed?"
        )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(YES_PROCEED[lg]))
    rec_label = "🔴 Recording: ON ($0.02)" if user_data[user_id]["recording_requested"] else "⚪ Recording: OFF (tap to enable $0.02)"
    markup.add(types.KeyboardButton(rec_label))
    markup.add(types.KeyboardButton(EDIT_DETAILS[lg]))
    bot.send_message(user_id, summary, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in YES_PROCEED.values())
def proceed_single_ivr(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)

    phone_number = user_data[user_id]["phone_number"]
    caller_id = user_data[user_id]["caller_id"]
    recording_requested = user_data[user_id].get("recording_requested", False)

    if user_data[user_id]["call_type"] == "single_ivr":
        gate = pre_call_check(user_id, phone_number, call_type="single")
        if not gate["allowed"]:
            bot.send_message(
                user_id, gate["message"],
                reply_markup=insufficient_balance_markup(user_id),
            )
            return

        # Charge recording fee if requested
        if recording_requested:
            from payment.views import debit_wallet as dw
            rec_result = dw(
                user_id, 0.02,
                description="Recording fee: single call",
                tx_type="REC",
            )
            if rec_result["status"] != 200:
                bot.send_message(user_id, "Failed to charge recording fee. Call proceeding without recording.")
                recording_requested = False

        if check_user_data(user_data, user_id) == "task":
            task = user_data[user_id]["task"]
            response = send_task_through_call(task, phone_number, caller_id, user_id, recording_requested=recording_requested)
            print(response)
            if response.status_code != 200:
                bot.send_message(user_id, PROCESSING_ERROR_MESSAGE[lg])
            else:
                rec_msg = " 🎙 Recording enabled." if recording_requested else ""
                bot.send_message(
                    user_id,
                    f"{SINGLE_CALL_INITIATED[lg]}{rec_msg}",
                    reply_markup=ivr_call_keyboard(user_id),
                )
            del user_data[user_id]["task"]

        else:
            pathway_id = user_data[user_id]["pathway_id"]
            response, status_code = send_call_through_pathway(
                pathway_id, phone_number, user_id, caller_id, recording_requested=recording_requested
            )
            if status_code != 200:
                bot.send_message(user_id, PROCESSING_ERROR_MESSAGE[lg])
            else:
                rec_msg = " 🎙 Recording enabled." if recording_requested else ""
                bot.send_message(
                    user_id,
                    f"{SINGLE_CALL_INITIATED[lg]}{rec_msg}",
                    reply_markup=ivr_call_keyboard(user_id),
                )

            del user_data[user_id]["pathway_id"]

    else:
        # Store recording preference for batch — will be used in start_batch_calls_now
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton(START_NOW[lg]))
        markup.add(KeyboardButton(SCHEDULE_FOR_LATER[lg]))
        bot.send_message(user_id, START_BULK_IVR[lg], reply_markup=markup)

    return


@bot.message_handler(func=lambda message: message.text in START_NOW.values())
def start_batch_calls_now(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    phone_number = user_data[user_id]["phone_number"]
    caller_id = user_data[user_id]["caller_id"]
    campaign_id = user_data[user_id]["campaign_id"]
    recording_requested = user_data[user_id].get("recording_requested", False)

    # Pre-call gate for bulk
    gate = pre_call_check_bulk(user_id, phone_number, call_type="bulk")
    if not gate["allowed"]:
        bot.send_message(
            user_id, gate["message"],
            reply_markup=insufficient_balance_markup(user_id),
        )
        return

    # Charge recording fee for all calls in batch
    total_calls = len(phone_number) if isinstance(phone_number, list) else 1
    if recording_requested:
        rec_total = 0.02 * total_calls
        from payment.views import debit_wallet as dw
        rec_result = dw(
            user_id, rec_total,
            description=f"Recording fee: batch of {total_calls} calls",
            tx_type="REC",
        )
        if rec_result["status"] != 200:
            bot.send_message(user_id, f"Failed to charge recording fee (${rec_total:.2f}). Proceeding without recording.")
            recording_requested = False

    if check_user_data(user_data, user_id) == "task":
        task = user_data[user_id]["task"]
        response = bulk_ivr_flow(
            call_data=phone_number,
            user_id=user_id,
            caller_id=caller_id,
            campaign_id=campaign_id,
            task=task,
            pathway_id=None,
            recording_requested=recording_requested,
        )
        del user_data[user_id]["task"]
    else:
        pathway_id = user_data[user_id]["pathway_id"]
        response = bulk_ivr_flow(
            call_data=phone_number,
            user_id=user_id,
            caller_id=caller_id,
            campaign_id=campaign_id,
            task=None,
            pathway_id=pathway_id,
            recording_requested=recording_requested,
        )
        del user_data[user_id]["pathway_id"]
    if response.status_code != 200:
        print("the following error occurred : ", response.json())
        del user_data[user_id]["pathway_id"]
        return

    rec_msg = f" 🎙 Recording enabled for {total_calls} calls." if recording_requested else ""
    bot.send_message(
        user_id, f"{CAMPAIGN_INITIATED[lg]}{rec_msg}", reply_markup=ivr_call_keyboard(user_id)
    )


geolocator = Nominatim(user_agent="timezone_bot")


# Function to get timezone from a city name
def get_timezone_from_city(city_name):
    try:
        geolocator = Nominatim(user_agent="timezone_bot")
        location = geolocator.geocode(city_name)
        if location:
            # Get latitude and longitude of the city
            latitude = location.latitude
            longitude = location.longitude

            # Use timezonefinder to get the timezone from lat/long
            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lng=longitude, lat=latitude)

            if timezone_str:
                timezone = pytz.timezone(timezone_str)
                print(f"Timezone for {city_name} is {timezone_str}")
                return timezone
            else:
                raise ValueError(f"Could not determine timezone for {city_name}")
        else:
            raise ValueError(f"City not found: {city_name}")
    except Exception as e:
        print(f"Error finding timezone for city {city_name}: {e}")
        return None


# Function to convert datetime from the user's timezone to UTC
def convert_datetime_to_target_timezone(input_datetime, city_name):
    try:
        dt_pattern = r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) (.+)"
        match = re.match(dt_pattern, input_datetime)
        if not match:
            return "Error: Invalid format. Please use YYYY-MM-DD HH:mm [City]."

        date_str, time_str, city = match.groups()
        datetime_str = f"{date_str} {time_str}"

        timezone = get_timezone_from_city(city.strip())
        if timezone is None:
            return "Error: Could not determine the timezone for the provided city."

        # Parse the datetime string into a datetime object
        user_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

        # Localize the datetime to the user's timezone
        user_datetime = timezone.localize(user_datetime)

        # Check if the datetime is in the future
        if user_datetime < datetime.now(timezone):
            return "The datetime must be in the future."

        # Convert the datetime to UTC
        utc_datetime = user_datetime.astimezone(pytz.utc)
        print("Datetime in UTC:", utc_datetime)

        return user_datetime, utc_datetime
    except Exception as e:
        print(f"Error in datetime conversion: {str(e)}")
        return "Please enter a valid datetime in the format YYYY-MM-DD HH:mm [City]."


# Handler for receiving datetime input for scheduling
def handle_datetime_input_for_schedule(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    datetime_input = message.text.strip()

    print(f"User {user_id} entered datetime: {datetime_input}")

    # Validate datetime input format and check if it's in the future
    try:
        # Convert to datetime object and check timezone
        result = convert_datetime_to_target_timezone(
            datetime_input, datetime_input.split()[-1]
        )  # Get city name from input
        if isinstance(result, str) and result.startswith("Error"):  # Check for errors
            raise ValueError(result)

        user_datetime, utc_time = (
            result  # Extract both the input city datetime and the UTC time
        )

        # Save the UTC time for scheduling (now it's a datetime object in UTC)
        user_data[user_id]["scheduled_time"] = utc_time

        print(f"Scheduled datetime confirmed for user {user_id}: {user_datetime}")

        # Proceed to reminder selection
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton(TEN_TWENTY_THIRTY_MINUTES_BEFORE[lg]))
        markup.add(KeyboardButton(NO_REMINDER[lg]))
        print("Asking for reminder preference.")
        user_data[user_id]["scheduled_time"] = utc_time
        user = TelegramUser.objects.get(user_id=user_id)
        print("Campaign ID : ", user_data[user_id]["campaign_id"])
        campaign_id = user_data[user_id]["campaign_id"]
        campaign = CampaignLogs.objects.get(campaign_id=campaign_id)
        print(campaign.campaign_name)
        call_data = user_data[user_id]["phone_number"]
        caller_id = user_data[user_id]["caller_id"]
        schedule_call = ScheduledCalls.objects.create(
            user_id=user,
            campaign_id=campaign,
            call_data=call_data,
            schedule_time=utc_time,
            caller_id=caller_id,
        )
        task, pathway_id = None, None
        if check_user_data(user_data, user_id) == "task":
            task = user_data[user_id]["task"]
            schedule_call.task = task

        else:
            pathway_id = user_data[user_id]["pathway_id"]
            schedule_call.pathway_id = pathway_id

        schedule_call.save()
        user_data[user_id]["call_time"] = utc_time
        user_data[user_id]["scheduled_call_id"] = schedule_call.id

        current_time = datetime.utcnow().replace(tzinfo=pytz.utc)

        delay_time = (utc_time - current_time).total_seconds()
        execute_bulk_ivr.schedule(args=(schedule_call.id,), delay=delay_time)

        bot.send_message(user_id, f"{CALL_SCHEDULED_SUCCESS[lg]}")

        scheduled_time_str = user_datetime.strftime("%Y-%m-%d %H:%M %Z")
        utc_time_str = utc_time.strftime("%Y-%m-%d %H:%M UTC")  # UTC time

        confirmation_message = (
            f"{SCHEDULED_CAMPAIGN[lg]}\n"
            f"{CAMPAIGN_NAME_LABEL[lg]} {campaign.campaign_name}\n"
            f"{RECIPIENTS[lg]} {user_data[user_id]['call_count']} numbers "
            f"\n{TIME_LABEL[lg]} (UTC): {scheduled_time_str}"
        )
        user_data[user_id]["confirmation_message"] = confirmation_message
        bot.send_message(
            user_id, "When would you like to receive a reminder?", reply_markup=markup
        )

    except Exception as e:
        print(f"Error with datetime input for user {user_id}: {str(e)}")
        bot.send_message(user_id, f"{INVALID_DATE_FORMAT[lg]}")
        schedule_for_later(message)


# Handler for setting reminders
@bot.message_handler(
    func=lambda message: message.text in TEN_TWENTY_THIRTY_MINUTES_BEFORE.values()
)
def handle_reminder(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    utc_time = user_data[user_id]["call_time"]  # Get scheduled call time in UTC
    schedule_call_id = user_data[user_id]["scheduled_call_id"]
    reminder_times = [10, 20, 30]  # Times for reminders: 10, 20, 30 minutes before

    # Get the current time in UTC and make it offset-aware
    now = datetime.utcnow().replace(tzinfo=pytz.utc)  # Make now UTC-aware
    time_diff = utc_time - now

    # Check if there's enough time to schedule reminders
    if time_diff < timedelta(minutes=5):
        bot.send_message(user_id, f"{CAMPAIGN_TOO_SOON_FOR_REMINDERS[lg]}")
        schedule_confirmation(message)
        return

    # Set reminders based on available time
    for minutes in reminder_times:
        if time_diff >= timedelta(minutes=minutes):
            reminder_time = utc_time - timedelta(minutes=minutes)
            delay = (
                reminder_time - now
            ).total_seconds()  # Calculate the delay in seconds
            send_reminder.schedule(args=(schedule_call_id, minutes), delay=delay)
        else:
            # If not enough time for this reminder, skip it
            print(f"Not enough time for {minutes}-minute reminder.")

    # Send final confirmation message
    schedule_confirmation(message)


# Handler for when no reminder is set
@bot.message_handler(func=lambda message: message.text in NO_REMINDER.values())
def schedule_confirmation(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    confirmation_message = user_data[user_id]["confirmation_message"]
    bot.send_message(
        user_id, confirmation_message, reply_markup=ivr_call_keyboard(user_id)
    )


@bot.message_handler(func=lambda message: message.text in SCHEDULE_FOR_LATER.values())
def schedule_for_later(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    print(f"User {user_id} selected 'Schedule for Later' option.")

    print("Sending datetime input prompt to user.")
    bot.send_message(user_id, SCHEDULE_TIMEZONE_HINT[lg], reply_markup=get_force_reply(), parse_mode="Markdown")

    bot.register_next_step_handler(message, handle_datetime_input_for_schedule)


def check_user_data(user_data, user_id):
    if "task" in user_data[user_id]:
        print("task")
        return "task"
    if "pathway_id" in user_data[user_id]:
        print("pathway_id")
        return "pathway_id"
    return None


@bot.message_handler(
    func=lambda message: message.text in NO_REMINDER.values()
    or message.text in TEN_TWENTY_THIRTY_MINUTES_BEFORE.values()
)
def handle_reminder_input_for_schedule(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    reminder_input = message.text.strip()

    print(f"User {user_id} selected reminder: {reminder_input}")

    if reminder_input == NO_REMINDER[lg]:
        user_data[user_id]["reminder"] = None
        print(f"User {user_id} chose no reminder.")
    elif reminder_input == TEN_TWENTY_THIRTY_MINUTES_BEFORE[lg]:
        user_data[user_id]["reminder"] = "10/20/30 Minutes Before"
        print(f"User {user_id} chose reminder: 10/20/30 minutes before.")

    # Final confirmation
    scheduled_time = user_data[user_id]["scheduled_time"]
    reminder = user_data[user_id].get("reminder", "No reminder")

    # Get additional info from user_data (campaign name, recipients)
    campaign_name = user_data[user_id].get("campaign_name", "Default Campaign")
    recipients = len(user_data[user_id].get("recipients", []))

    # Ensure scheduled_time is formatted for display (use .strftime() here)
    confirmation_message = f"✅ Scheduled Campaign:\n🏷️ Name: {campaign_name}\n👥 Recipients: {recipients} numbers\n🕒 Time: {scheduled_time.strftime('%Y-%m-%d %H:%M %Z')}\n⏰ Reminder: {reminder}"

    print(f"Sending confirmation to user {user_id}:\n{confirmation_message}")
    bot.send_message(user_id, confirmation_message)
    bot.send_message(user_id, f"{CAMPAIGN_SCHEDULED_SUCCESS[lg]}")


@bot.message_handler(func=lambda message: message.text in SINGLE_IVR.values())
def handle_single_ivr_flow_call(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["call_type"] = "single_ivr"
    user_data[user_id]["step"] = "phone_number_input"
    subscribed_users_message_ivr(user_id)


@bot.message_handler(func=lambda message: message.text in BULK_CALL.values())
def handle_bulk_ivr_flow_call(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["call_type"] = "bulk_ivr"
    user_data[user_id]["step"] = "get_batch_numbers"
    subscribed_users_message_ivr(user_id)


def subscribed_users_message_ivr(user_id):
    user = TelegramUser.objects.get(user_id=user_id)
    lg = get_user_language(user_id)
    subscription = UserSubscription.objects.get(user_id=user)
    if subscription.subscription_status == "active":
        plan = subscription.plan_id
        node_access = (
            f"{FULL_NODE_ACCESS[lg]}"
            if plan.call_transfer
            else f"{PARTIAL_NODE_ACCESS[lg]}"
        )
        call_transfer_node = "✅" if plan.call_transfer else "❌"

        if plan.single_ivr_minutes == MAX_INFINITY_CONSTANT:
            single_calls = f"{UNLIMITED_SINGLE_IVR[lg]}"
        else:
            single_calls = f"{plan.single_ivr_minutes:.4f} {SINGLE_IVR_MINUTES[lg]}"
        if plan.number_of_bulk_call_minutes is None:
            bulk_calls = NO_BULK_MINS_LEFT[lg]
        else:
            bulk_calls = (
                f"{subscription.bulk_ivr_calls_left:.2f} / "
                f"{plan.number_of_bulk_call_minutes:.2f} {BULK_IVR_CALLS[lg]}"
            )
        current_day_of_subscription = get_subscription_day(subscription)

        if plan.plan_price == 0:
            msg = (
                f"🆓 Free Trial \n"
                f"⏳ Status: Day {current_day_of_subscription} of {plan.validity_days}\n"
                f"☎️ Quick Calls Used: {subscription.single_ivr_left}\n"
                f"😊 Note: Subscribe after trial! "
            )
        else:
            msg = (
                f"Welcome! Let's get started:\n"
                f"🌟 Active Plan: {plan.name} ({current_day_of_subscription} of {plan.validity_days} Days)\n"
                f"📞 Quick Calls: {single_calls}\n"
                f"⏱️ Bulk Calls: {bulk_calls}\n"
                f"💳  Note: Extra usage auto-deducts from wallet at $0.35/min. International calls billed per-minute."
            )

        bot.send_message(user_id, msg, reply_markup=get_task_type_keyboard(user_id))
    else:
        msg = (
            "💵 Pay-as-you-go pricing (wallet deduction): \n"
            "📞 Single IVR: $0.35/min\n"
            "📋 Bulk IVR: $0.35/min\n"
            "🌍 International: $0.45-$0.85/min\n"
            "🛑 You need at least $0.70 in your wallet (covers 2 minutes) before making a call."
        )
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add(types.KeyboardButton(MAKE_IVR_CALL[lg]))
        markup.add(types.KeyboardButton(BILLING_AND_SUBSCRIPTION[lg]))
        bot.send_message(user_id, msg, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in MAKE_IVR_CALL.values())
def handle_make_ivr_call(message):

    user_id = message.chat.id
    lg = get_user_language(user_id)
    msg = (
        f"Choose task type:\n"
        f"{AI_MADE_TASKS[lg]} (e.g., surveys)\n"
        f"{CUSTOM_MADE_TASKS[lg]} (personalized scripts)\n"
        f"{CREATE_TASK[lg]} (new task)"
    )
    bot.send_message(user_id, msg, reply_markup=get_task_type_keyboard(user_id))


@bot.message_handler(func=lambda message: message.text in CREATE_TASK.values())
def handle_create_task(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["step"] = "create_task_flow"
    bot.send_message(
        user_id,
        f"{CREATE_TASK_PROMPT[lg]}\n"
        f"{AI_ASSISTED_FLOW[lg]}\n"
        f"{ADVANCED_USER_FLOW[lg]}\n",
        reply_markup=get_create_task_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in CREATE_IVR_FLOW_AI.values())
def handle_create_ivr_flow_ai(message):
    initiate_ai_assisted_flow(message)


@bot.message_handler(func=lambda message: message.text in VIEW_FLOWS_AI.values())
def handle_view_flow_ai(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    tasks = AI_Assisted_Tasks.objects.filter(user_id=user_id).values("task_name", "id")
    markup = types.InlineKeyboardMarkup()

    for task in tasks:
        task_name = task["task_name"]
        task_id = task["id"]
        markup.add(
            types.InlineKeyboardButton(
                task_name, callback_data=f"displaytask_{task_id}"
            )
        )

    bot.send_message(user_id, DISPLAY_IVR_FLOWS[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("displaytask_"))
def handle_call_back_view_task(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    task_id = call.data.split("_")[1]
    task = AI_Assisted_Tasks.objects.get(id=task_id)
    msg = (
        f"{CAMPAIGN_NAME_LABEL[lg]} {task.task_name}\n\n"
        f"{TASK_DESCRIPTION[lg]} {task.task_description}"
    )
    bot.send_message(
        user_id, msg, reply_markup=ai_assisted_user_flow_keyboard(user_id)
    )


@bot.message_handler(func=lambda message: message.text in DELETE_FLOW_AI.values())
def handle_delete_flow_ai(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    tasks = AI_Assisted_Tasks.objects.filter(user_id=user_id).values("task_name", "id")
    markup = types.InlineKeyboardMarkup()

    for task in tasks:
        task_name = task["task_name"]
        task_id = task["id"]
        markup.add(
            types.InlineKeyboardButton(task_name, callback_data=f"deletetask_{task_id}")
        )

    bot.send_message(user_id, DISPLAY_IVR_FLOWS[lg], reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("deletetask_"))
def handle_call_back_view_task(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    task_id = call.data.split("_")[1]

    try:
        task = AI_Assisted_Tasks.objects.get(id=task_id)
        task.delete()

        bot.send_message(
            user_id,
            "Deleted Successfully!",
            reply_markup=ai_assisted_user_flow_keyboard(),
        )
    except AI_Assisted_Tasks.DoesNotExist:
        bot.send_message(
            user_id,
            "Task not found. Please try again.",
            reply_markup=ai_assisted_user_flow_keyboard(user_id),
        )


# ---------------------campaign management----------------------


@bot.message_handler(func=lambda message: message.text in CAMPAIGN_MANAGEMENT.values())
def initiate_campaign_management_flow(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id,
        CAMPAIGN_MANAGEMENT_WELCOME[lg],
        reply_markup=get_campaign_management_keyboard(user_id),
    )


@bot.message_handler(func=lambda message: message.text in RETURN_HOME.values())
def handle_return_home(message):
    user_id = message.chat.id
    initiate_campaign_management_flow(message)


@bot.message_handler(func=lambda message: message.text in ACTIVE_CAMPAIGNS.values())
def handle_active_campaign(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    scheduled_campaigns = ScheduledCalls.objects.filter(
        user_id=user_id, call_status=True
    )
    if not scheduled_campaigns.exists():
        markup = types.InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(RETURN_HOME[lg], callback_data="back_to_campaign_home"))
        bot.send_message(user_id, f"🚀 No active campaigns yet.", reply_markup=markup)
        return
    details = ""
    markup = types.InlineKeyboardMarkup()
    for campaign in scheduled_campaigns:
        campaign_details = CampaignLogs.objects.get(campaign_id=campaign.campaign_id_id)
        campaign_name = campaign_details.campaign_name
        task_name = ""
        if campaign.pathway_id:
            task = Pathways.objects.get(pathway_id=campaign.pathway_id)
            task_name = task.pathway_name
        if campaign.task:
            task = AI_Assisted_Tasks.objects.get(task_description=campaign.task)
            task_name = task.task_name
        details += (
            f"{CAMPAIGN_NAME_LABEL[lg]} {campaign_name}\n\n"
            f"{TASK[lg]} {task_name}\n"
            f"{START_TIME[lg]} {campaign_details.start_date}\n\n"
        )
        markup.add(
            InlineKeyboardButton(
                campaign_name, callback_data=f"activecampaign_{campaign.campaign_id_id}"
            )
        )
    bot.send_message(user_id, details, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("activecampaign_"))
def handle_view_active_campaign_flow(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    data = call.data.split("_")
    campaign_id = data[1]

    campaign = CampaignLogs.objects.get(campaign_id=campaign_id)
    schedule = ScheduledCalls.objects.get(campaign_id=campaign)
    if schedule.pathway_id:
        task = Pathways.objects.get(pathway_id=schedule.pathway_id)
        task_name = task.pathway_name
    if schedule.task:
        task = AI_Assisted_Tasks.objects.get(task_description=schedule.task)
        task_name = task.task_name
    details = (
        f"{NAME[lg]}: {campaign.campaign_name}\n"
        f"{TASK[lg]} {task_name}\n"
        f"{START_TIME[lg]} {campaign.start_date}\n"
        f"{TOTAL_NUMBERS[lg]} {campaign.total_calls}\n\n"
    )
    markup = ReplyKeyboardMarkup()
    markup.add(KeyboardButton(RETURN_TO_ACTIVE_CAMPAIGNS[lg]))
    markup.add(RETURN_HOME[lg])
    bot.send_message(user_id, details)
    bot.send_message(
        user_id, ACTIVE_CAMPAIGNS_CANNOT_BE_MODIFIED[lg], reply_markup=markup
    )


@bot.message_handler(
    func=lambda message: message.text in RETURN_TO_ACTIVE_CAMPAIGNS.values()
)
def handle_return_to_active_campaigns(message):
    handle_active_campaign(message)


@bot.message_handler(func=lambda message: message.text in GO_BACK.values())
def handle_go_back(message):
    handle_scheduled_campaign(message)


@bot.message_handler(func=lambda message: message.text in SCHEDULED_CAMPAIGNS.values())
def handle_scheduled_campaign(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    scheduled_campaigns = ScheduledCalls.objects.filter(
        user_id=user_id, call_status=False
    )
    if not scheduled_campaigns.exists():
        markup = types.InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(RETURN_HOME[lg], callback_data="back_to_campaign_home"))
        bot.send_message(user_id, f"🗓️ No scheduled campaigns yet.", reply_markup=markup)
        return
    details = ""
    markup = types.InlineKeyboardMarkup()
    for campaign in scheduled_campaigns:
        campaign_name = CampaignLogs.objects.get(
            campaign_id=campaign.campaign_id_id
        ).campaign_name
        task_name = ""
        if campaign.pathway_id:
            task = Pathways.objects.get(pathway_id=campaign.pathway_id)
            task_name = task.pathway_name
        if campaign.task:
            task = AI_Assisted_Tasks.objects.get(task_description=campaign.task)
            task_name = task.task_name
        details += (
            f"{CAMPAIGN_NAME_LABEL[lg]} {campaign_name}\n\n"
            f"{TASK[lg]} {task_name}\n"
            f"{SCHEDULED_TIME[lg]} {campaign.schedule_time}\n\n"
        )

        data = f"viewcampaign_{campaign.campaign_id_id}"
        markup.add(InlineKeyboardButton(campaign_name, callback_data=data))
    markup.add(
        InlineKeyboardButton(RETURN_HOME[lg], callback_data="back_to_campaign_home")
    )
    bot.send_message(user_id, details, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_campaign_home")
def back_to_campaign_home(call):
    initiate_campaign_management_flow(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("viewcampaign_"))
def handle_view_campaign_flow(call):
    user_id = call.message.chat.id
    lg = get_user_language(user_id)
    data = call.data.split("_")
    campaign_id = data[1]

    campaign = CampaignLogs.objects.get(campaign_id=campaign_id)
    schedule = ScheduledCalls.objects.get(campaign_id=campaign)
    user_data[user_id]["scheduled_call_id"] = schedule.id

    if schedule.pathway_id:
        task = Pathways.objects.get(pathway_id=schedule.pathway_id)
        task_name = task.pathway_name

    if schedule.task:
        task = AI_Assisted_Tasks.objects.get(task_description=schedule.task)
        task_name = task.task_name

    details = (
        f"{NAME[lg]}: {campaign.campaign_name}\n"
        f"{TASK[lg]} {task_name}\n"
        f"{SCHEDULED_TIME[lg]} {schedule.schedule_time}\n"
        f"{TOTAL_NUMBERS[lg]} {campaign.total_calls}\n\n"
        f"{WHAT_WOULD_YOU_LIKE_TO_DO[lg]}"
    )

    user_data[user_id]["phone_number"] = schedule.call_data
    user_data[user_id]["caller_id"] = schedule.caller_id
    user_data[user_id]["campaign_id"] = campaign_id
    if schedule.task:
        user_data[user_id]["task"] = schedule.task
    elif schedule.pathway_id:
        user_data[user_id]["pathway_id"] = schedule.pathway_id

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(CANCEL_CAMPAIGN[lg]))
    markup.add(KeyboardButton(START_NOW[lg]))
    markup.add(KeyboardButton(GO_BACK[lg]))
    bot.send_message(user_id, details, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in CANCEL_CAMPAIGN.values())
def cancel_scheduled_campaign_confirmation(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    markup = ReplyKeyboardMarkup()
    markup.add(KeyboardButton(YES_CANCEL[lg]))
    markup.add(KeyboardButton(NO_GO_BACK[lg]))
    bot.send_message(user_id, CONFIRM_CANCEL_CAMPAIGN[lg], reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in YES_CANCEL.values())
def cancel_scheduled_campaign(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    schedule_call_id = user_data[user_id]["scheduled_call_id"]
    result = cancel_scheduled_call(schedule_call_id)
    print("Cancel Campaign Result: ", result)
    bot.send_message(
        user_id,
        CAMPAIGN_CANCELED[lg],
        reply_markup=get_campaign_management_keyboard(user_id),
    )


# ------------------------------DTMF Inbox---------------------------------
@bot.message_handler(func=lambda message: message.text in INBOX.values())
def handle_inbox(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)

    bot.send_message(
        user_id, WELCOME_PROMPT_INBOX[lg], reply_markup=inbox_keyboard(user_id)
    )


@bot.message_handler(func=lambda message: message.text in SINGLE_CALL.values())
def handle_single_call_inbox(message):
    user_id = message.chat.id
    lg = get_user_language(user_id)
    bot.send_message(
        user_id, ENTER_PHONE_OR_CALL_ID[lg], reply_markup=get_force_reply()
    )


def start_bot():
    """
    Start the Telegram bot and initiate infinity polling.
    """
    bot.infinity_polling()
