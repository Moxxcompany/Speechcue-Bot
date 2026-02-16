"""
Runtime test: Actually invoke handlers with fake messages to detect crashes.
"""
import os, sys, json, traceback
sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TelegramBot.settings")
from dotenv import load_dotenv
load_dotenv("/app/.env")
import django
django.setup()

from bot.bot_config import bot as telegram_bot
import bot.telegrambot
from telebot import types
from user.models import TelegramUser
from payment.models import UserSubscription

# Get test user
test_user = TelegramUser.objects.first()
TEST_USER_ID = test_user.user_id if test_user else 999
print(f"Test user: {TEST_USER_ID}")

# Make sure user_data is populated
from bot.telegrambot import user_data
if TEST_USER_ID not in user_data:
    user_data[TEST_USER_ID] = {}

def make_fake_message(text, chat_id=TEST_USER_ID):
    """Create a minimal fake Message object."""
    msg = types.Message(
        message_id=1,
        from_user=types.User(id=chat_id, is_bot=False, first_name="Test"),
        date=0,
        chat=types.Chat(id=chat_id, type="private"),
        content_type="text",
        options={"text": text},
        json_string=""
    )
    return msg

def make_fake_callback(data, chat_id=TEST_USER_ID):
    """Create a minimal fake CallbackQuery object."""
    msg = make_fake_message("test", chat_id)
    cb = types.CallbackQuery(
        id="1",
        from_user=types.User(id=chat_id, is_bot=False, first_name="Test"),
        data=data,
        chat_instance="test",
        message=msg,
        json_string=""
    )
    return cb

# Monkey-patch bot.send_message and bot.answer_callback_query to not actually call Telegram
original_send = telegram_bot.send_message
original_send_photo = telegram_bot.send_photo
original_answer = telegram_bot.answer_callback_query

sent_messages = []

def mock_send_message(chat_id, text, **kwargs):
    sent_messages.append({"chat_id": chat_id, "text": str(text)[:100]})
    return types.Message(
        message_id=2,
        from_user=types.User(id=0, is_bot=True, first_name="Bot"),
        date=0,
        chat=types.Chat(id=chat_id, type="private"),
        content_type="text",
        options={"text": str(text)[:50]},
        json_string=""
    )

def mock_send_photo(chat_id, photo, **kwargs):
    sent_messages.append({"chat_id": chat_id, "text": "[PHOTO]"})
    return None

def mock_answer_callback(callback_query_id, **kwargs):
    pass

telegram_bot.send_message = mock_send_message
telegram_bot.send_photo = mock_send_photo
telegram_bot.answer_callback_query = mock_answer_callback

print("=" * 70)
print("RUNTIME HANDLER EXECUTION TEST")
print("=" * 70)

results = {"passed": [], "failed": []}

def test_message_handler(text, description):
    """Find matching handler and invoke it."""
    sent_messages.clear()
    for handler in telegram_bot.message_handlers:
        try:
            msg = make_fake_message(text)
            if handler.get("filters") and handler["filters"].get("func"):
                if handler["filters"]["func"](msg):
                    # Found matching handler, try to invoke it
                    try:
                        handler["function"](msg)
                        results["passed"].append(description)
                        print(f"  ✅ {description:40s} → {handler['function'].__name__}")
                        return True
                    except Exception as e:
                        err = str(e)[:120]
                        results["failed"].append((description, handler["function"].__name__, err))
                        print(f"  ❌ {description:40s} → {handler['function'].__name__}: {err}")
                        return False
        except Exception:
            pass
    print(f"  ⚠️  {description:40s} → No matching handler found")
    results["failed"].append((description, "N/A", "No handler"))
    return False

def test_callback_handler(data, description):
    """Find matching callback handler and invoke it."""
    sent_messages.clear()
    for handler in telegram_bot.callback_query_handlers:
        try:
            cb = make_fake_callback(data)
            if handler.get("filters") and handler["filters"].get("func"):
                if handler["filters"]["func"](cb):
                    try:
                        handler["function"](cb)
                        results["passed"].append(description)
                        print(f"  ✅ {description:40s} → {handler['function'].__name__}")
                        return True
                    except Exception as e:
                        err = str(e)[:120]
                        results["failed"].append((description, handler["function"].__name__, err))
                        print(f"  ❌ {description:40s} → {handler['function'].__name__}: {err}")
                        return False
        except Exception:
            pass
    print(f"  ⚠️  {description:40s} → No matching handler found")
    results["failed"].append((description, "N/A", "No handler"))
    return False

# ===== Test Main Menu Buttons =====
print("\n--- MAIN MENU BUTTONS ---")
test_message_handler("📞 Phone Numbers", "Phone Numbers Hub")
test_message_handler("🎙 IVR Flows", "IVR Flows Menu")
test_message_handler("☎️ Make a Call", "Make a Call Menu")
test_message_handler("📋 Campaigns", "Campaigns Menu")
test_message_handler("📬 Inbox", "Inbox Hub")
test_message_handler("💰 Wallet & Billing", "Wallet & Billing Hub")
test_message_handler("Account 👤", "Account Menu")
test_message_handler("Help ℹ️", "Help Menu")

# ===== Test Inline Callback Buttons =====
print("\n--- PHONE NUMBERS HUB INLINE ---")
test_callback_handler("buy_number", "Buy Number")
test_callback_handler("my_numbers", "My Numbers")
test_callback_handler("sms_inbox", "SMS Inbox")

print("\n--- INBOX HUB INLINE ---")
test_callback_handler("call_recordings", "Call Recordings")
test_callback_handler("dtmf_responses_hub", "DTMF Responses Hub")
test_callback_handler("call_history", "Call History")

print("\n--- WALLET & BILLING INLINE ---")
test_callback_handler("top_up_wallet", "Top Up Wallet")
test_callback_handler("transaction_history", "Transaction History")
test_callback_handler("view_subscription", "View Subscription")
test_callback_handler("update_subscription", "Update Subscription")
test_callback_handler("check_wallet", "Check Wallet")

print("\n--- NAVIGATION CALLBACKS ---")
test_callback_handler("back_to_welcome_message", "Back to Welcome")
test_callback_handler("inbox_hub_back", "Inbox Hub Back")
test_callback_handler("wallet_hub_back", "Wallet Hub Back")
test_callback_handler("phone_hub_back", "Phone Hub Back")
test_callback_handler("back_to_billing", "Back to Billing")
test_callback_handler("back_ivr_flow", "Back IVR Flow")
test_callback_handler("back_ivr_call", "Back IVR Call")
test_callback_handler("back_account", "Back Account")
test_callback_handler("back_to_campaign_home", "Back Campaign Home")

print("\n--- ONBOARDING ---")
test_callback_handler("activate_free_plan", "Activate Free Plan")
test_callback_handler("how_it_works", "How It Works")
test_callback_handler("activate_subscription", "Activate Subscription")

print("\n--- ACCOUNT SUB-MENUS ---")
test_message_handler("Profile 👤", "Profile")
test_message_handler("Settings ⚙", "Settings")
test_message_handler("Back ↩️", "Back Button (Main)")

print("\n--- IVR SUB-MENUS ---")
test_message_handler("🤖 AI Assisted Flow", "AI Assisted Flow")
test_message_handler("🛠️ Advanced User Flow", "Advanced User Flow")
test_message_handler("Single IVR Call 🟢", "Single IVR Call")
test_message_handler("Bulk IVR Call 🔵", "Bulk IVR Call")
test_message_handler("Call Status ℹ", "Call Status")

print("\n--- CAMPAIGN SUB-MENUS ---")
test_message_handler("🗓️ Scheduled Campaigns", "Scheduled Campaigns")
test_message_handler("🚀 Active Campaigns", "Active Campaigns")
test_message_handler("🏠 Return Home", "Return Home")

print("\n--- PLAN & PAYMENT ---")
test_callback_handler("change_language", "Change Language")
test_callback_handler("help", "Help Callback")
test_callback_handler("create_ivr_flow", "Create IVR Flow Callback")

# ===== Summary =====
print("\n" + "=" * 70)
print(f"RESULTS: {len(results['passed'])} PASSED | {len(results['failed'])} FAILED")
print("=" * 70)

if results["failed"]:
    print("\nFAILED HANDLERS:")
    for desc, handler, err in results["failed"]:
        print(f"  ❌ {desc} ({handler}): {err}")

# Restore original methods
telegram_bot.send_message = original_send
telegram_bot.send_photo = original_send_photo
telegram_bot.answer_callback_query = original_answer
