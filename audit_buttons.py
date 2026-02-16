"""
Comprehensive bot button handler audit.

This script simulates user interactions by directly invoking the bot handlers 
to identify which ones fail or are unresponsive.
"""
import os
import sys
import json
import traceback

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TelegramBot.settings")

from dotenv import load_dotenv
load_dotenv("/app/.env")

import django
django.setup()

# Import the bot and all handlers
from bot.bot_config import bot
import bot.telegrambot  # Registers all handlers

from telebot import types

# We'll use a fake user_id that exists in the DB
from user.models import TelegramUser

print("="*60)
print("BOT BUTTON HANDLER AUDIT")
print("="*60)

# Get an existing user for testing
test_users = TelegramUser.objects.all()[:1]
if not test_users:
    print("No users found in DB. Creating a test user...")
    test_user = TelegramUser.objects.create(user_id=999999999, user_name="test_audit")
    TEST_USER_ID = 999999999
else:
    test_user = test_users[0]
    TEST_USER_ID = test_user.user_id

print(f"Test user: {TEST_USER_ID} ({test_user.user_name})")
print()

# Get all registered handlers  
message_handlers = bot.message_handlers
callback_handlers = bot.callback_query_handlers

print(f"Registered message handlers: {len(message_handlers)}")
print(f"Registered callback handlers: {len(callback_handlers)}")
print()

# ======== Test Main Menu Reply Keyboard Buttons ========
from translations.translations import *

main_menu_buttons = [
    ("📞 Phone Numbers", "PHONE_NUMBERS_MENU"),
    ("🎙 IVR Flows", "IVR_FLOWS_MENU"),
    ("☎️ Make a Call", "MAKE_CALL_MENU"),
    ("📋 Campaigns", "CAMPAIGNS_MENU"),
    ("📬 Inbox", "INBOX_MENU"),
    ("💰 Wallet & Billing", "WALLET_AND_BILLING"),
    ("Account 👤", "ACCOUNT"),
    ("Help ℹ️", "HELP"),
]

print("=" * 60)
print("MAIN MENU BUTTON HANDLER MATCHING")
print("=" * 60)

for btn_text, translation_name in main_menu_buttons:
    # Check if any message handler would match this text
    matched = False
    handler_name = "N/A"
    for handler in message_handlers:
        try:
            # Create a fake message object
            fake_msg = types.Message(
                message_id=1,
                from_user=types.User(id=TEST_USER_ID, is_bot=False, first_name="Test"),
                date=0,
                chat=types.Chat(id=TEST_USER_ID, type="private"),
                content_type="text",
                options={"text": btn_text},
                json_string=""
            )
            # Test the filter function
            if handler["function"].__name__ != "trigger_back" and handler.get("filters") and handler["filters"].get("func"):
                try:
                    result = handler["filters"]["func"](fake_msg)
                    if result:
                        matched = True
                        handler_name = handler["function"].__name__
                        break
                except Exception:
                    pass
        except Exception:
            pass
    
    status = "✅ MATCHED" if matched else "❌ NO HANDLER"
    print(f"  {btn_text:30s} → {status} ({handler_name})")

print()

# ======== Test Inline Callback Buttons ========
print("=" * 60)
print("INLINE CALLBACK BUTTON HANDLER MATCHING")
print("=" * 60)

# All callback_data values used in keyboard_menus.py and telegrambot.py
callback_buttons = [
    # Phone Numbers hub
    ("buy_number", "Phone Numbers > Buy Number"),
    ("my_numbers", "Phone Numbers > My Numbers"),
    ("sms_inbox", "Phone Numbers > SMS Inbox"),
    # Inbox hub  
    ("call_recordings", "Inbox > Call Recordings"),
    ("dtmf_responses_hub", "Inbox > DTMF Responses"),
    ("call_history", "Inbox > Call History"),
    # Wallet & Billing hub
    ("top_up_wallet", "Wallet > Top Up"),
    ("transaction_history", "Wallet > Transaction History"),
    ("view_subscription", "Wallet > View Subscription"),
    ("update_subscription", "Wallet > Upgrade Plan"),
    # Navigation backs
    ("back_to_welcome_message", "Back to Main Menu"),
    ("inbox_hub_back", "Back to Inbox Hub"),
    ("wallet_hub_back", "Back to Wallet Hub"),
    ("phone_hub_back", "Back to Phone Hub"),
    ("back_to_billing", "Back to Billing"),
    ("back_ivr_flow", "Back to IVR Flow"),
    ("back_ivr_call", "Back to IVR Call"),
    ("back_account", "Back to Account"),
    ("back_to_campaign_home", "Back to Campaign Home"),
    ("back_to_handle_call_status", "Back to Call Status"),
    # Onboarding
    ("activate_free_plan", "Onboarding: Free Plan"),
    ("activate_subscription", "Activate Subscription"),
    ("how_it_works", "How It Works"),
    # Terms
    ("accept_terms", "Accept Terms"),
    ("decline_terms", "Decline Terms"),
    ("view_terms_new", "View Terms (New)"),
    ("view_terms", "View Terms"),
    ("exit_setup", "Exit Setup"),
    # Plan management
    ("check_wallet", "Check Wallet"),
    ("payment_option", "Payment Option"),
    ("cancel_plan_upgrade", "Cancel Upgrade"),
    ("continue_plan_upgrade", "Continue Upgrade"),
    ("back_to_plan_names", "Back to Plan Names"),
    ("back_to_view_terms", "Back to View Terms"),
    ("back_to_handle_payment", "Back to Handle Payment"),
    # Actions
    ("create_ivr_flow", "Create IVR Flow"),
    ("trigger_single_flow", "Trigger Single Flow"),
    ("change_language", "Change Language"),
    ("help", "Help"),
    ("main_menu", "Main Menu"),
    ("sms_clear_read", "Clear Read SMS"),
    # Add another condition / save conditions
    ("add_another_condition", "Add Another Condition"),
    ("save_conditions", "Save Conditions"),
    ("custom_condition", "Custom Condition"),
    # Phone number mgmt (dynamic prefix tested separately)
    ("buynum_US_local", "Buy US Local Number"),
    ("buynum_US_tollfree", "Buy US Toll-Free"),
    ("buynum_CA_local", "Buy CA Local Number"),
    ("buynum_back", "Buy Number Back"),
    ("buynum_pay_wallet", "Buy Number Pay Wallet"),
    ("buynum_pay_crypto", "Buy Number Pay Crypto"),
    ("buynum_pay_insufficient", "Buy Number Pay Insufficient"),
]

for cb_data, description in callback_buttons:
    matched = False
    handler_name = "N/A"
    for handler in callback_handlers:
        try:
            # Create a fake callback query
            fake_call = types.CallbackQuery(
                id="1",
                from_user=types.User(id=TEST_USER_ID, is_bot=False, first_name="Test"),
                data=cb_data,
                chat_instance="test",
                message=types.Message(
                    message_id=1,
                    from_user=types.User(id=TEST_USER_ID, is_bot=False, first_name="Test"),
                    date=0,
                    chat=types.Chat(id=TEST_USER_ID, type="private"),
                    content_type="text",
                    options={"text": "test"},
                    json_string=""
                ),
                json_string=""
            )
            if handler.get("filters") and handler["filters"].get("func"):
                result = handler["filters"]["func"](fake_call)
                if result:
                    matched = True
                    handler_name = handler["function"].__name__
                    break
        except Exception as e:
            pass
    
    status = "✅" if matched else "❌ MISSING"
    print(f"  {cb_data:35s} {status:12s} → {handler_name:40s} ({description})")

print()

# ======== Test Sub-Menu Reply Keyboard Buttons ========
print("=" * 60)
print("SUB-MENU BUTTON HANDLER MATCHING")
print("=" * 60)

submenu_buttons = [
    # Account sub-menu
    (PROFILE.get("English", ""), "Profile"),
    (SETTINGS.get("English", ""), "Settings"),
    (USER_FEEDBACK.get("English", ""), "User Feedback"),
    (BACK_BUTTON.get("English", ""), "Back Button"),
    # IVR Flow sub-menu
    (AI_ASSISTED_FLOW_KEYBOARD.get("English", ""), "AI Assisted Flow"),
    (ADVANCED_USER_FLOW_KEYBOARD.get("English", ""), "Advanced Flow"),
    # IVR Call sub-menu
    (SINGLE_IVR.get("English", ""), "Single IVR"),
    (BULK_CALL.get("English", ""), "Bulk Call"),
    (CALL_STATUS.get("English", ""), "Call Status"),
    # Advanced Flow sub-menu
    (CREATE_IVR_FLOW.get("English", ""), "Create IVR Flow"),
    (VIEW_FLOWS.get("English", ""), "View Flows"),
    (DELETE_FLOW.get("English", ""), "Delete Flow"),
    # Campaign sub-menu
    (SCHEDULED_CAMPAIGNS.get("English", ""), "Scheduled Campaigns"),
    (ACTIVE_CAMPAIGNS.get("English", ""), "Active Campaigns"),
    (RETURN_HOME.get("English", ""), "Return Home"),
    # Account inner
    (BILLING_AND_SUBSCRIPTION.get("English", ""), "Billing & Subscription"),
    (JOIN_CHANNEL.get("English", ""), "Join Channel"),
    (HELP.get("English", ""), "Help"),
    (TOP_UP.get("English", ""), "Top Up"),
    (DTMF_INBOX.get("English", ""), "DTMF Inbox"),
    # Old menu items (might conflict)
    (IVR_FLOW.get("English", ""), "IVR Flow (old)"),
    (IVR_CALL.get("English", ""), "IVR Call (old)"),
    (ACCOUNT.get("English", ""), "Account"),
    (CAMPAIGN_MANAGEMENT.get("English", ""), "Campaign Management"),
    (INBOX.get("English", "") if "English" in INBOX else "", "Inbox (old)"),
]

for btn_text, description in submenu_buttons:
    if not btn_text:
        print(f"  {'(empty text)':30s} ⚠️  SKIP ({description})")
        continue
    
    matched = False
    handler_name = "N/A"
    for handler in message_handlers:
        try:
            fake_msg = types.Message(
                message_id=1,
                from_user=types.User(id=TEST_USER_ID, is_bot=False, first_name="Test"),
                date=0,
                chat=types.Chat(id=TEST_USER_ID, type="private"),
                content_type="text",
                options={"text": btn_text},
                json_string=""
            )
            if handler.get("filters") and handler["filters"].get("func"):
                try:
                    result = handler["filters"]["func"](fake_msg)
                    if result:
                        matched = True
                        handler_name = handler["function"].__name__
                        break
                except Exception:
                    pass
        except Exception:
            pass
    
    status = "✅" if matched else "❌ NO HANDLER"
    print(f"  {btn_text:35s} {status:12s} → {handler_name:30s} ({description})")

print()
print("=" * 60)
print("AUDIT COMPLETE")
print("=" * 60)
