"""
Deep E2E test — patches bot.send_message to verify responses are actually sent.
"""
import os, sys, json, time, traceback
sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TelegramBot.settings")
from dotenv import load_dotenv
load_dotenv("/app/.env")
import django
django.setup()

from bot.bot_config import bot as telegram_bot
import bot.telegrambot as tg_module
from telebot import types

USER_ID = 5590563715

# Track all send_message calls
original_send = telegram_bot.send_message
original_send_photo = telegram_bot.send_photo
original_edit = telegram_bot.edit_message_text
original_answer = telegram_bot.answer_callback_query

responses = []

def mock_send(chat_id, text, **kwargs):
    responses.append({"type": "send", "chat_id": chat_id, "text": str(text)[:80]})
    return types.Message(
        message_id=2, from_user=types.User(id=0, is_bot=True, first_name="Bot"),
        date=0, chat=types.Chat(id=chat_id, type="private"),
        content_type="text", options={"text": str(text)[:50]}, json_string=""
    )

def mock_send_photo(chat_id, photo, **kwargs):
    responses.append({"type": "photo", "chat_id": chat_id})
    return None

def mock_edit(text, chat_id=None, message_id=None, **kwargs):
    responses.append({"type": "edit", "chat_id": chat_id, "text": str(text)[:80]})
    return None

def mock_answer(cb_id, **kwargs):
    responses.append({"type": "answer_cb", "id": cb_id})

telegram_bot.send_message = mock_send
telegram_bot.send_photo = mock_send_photo
telegram_bot.edit_message_text = mock_edit
telegram_bot.answer_callback_query = mock_answer

def make_msg(text):
    return types.Message(
        message_id=1, from_user=types.User(id=USER_ID, is_bot=False, first_name="Ray"),
        date=0, chat=types.Chat(id=USER_ID, type="private"),
        content_type="text", options={"text": text}, json_string=""
    )

def make_cb(data):
    msg = make_msg("previous")
    return types.CallbackQuery(
        id="999", from_user=types.User(id=USER_ID, is_bot=False, first_name="Ray"),
        data=data, chat_instance="test", message=msg, json_string=""
    )

def test_handler(name, update_type, value):
    """Test a handler and verify it produces a response."""
    responses.clear()
    try:
        if update_type == "message":
            update = types.Update(
                update_id=1, message=make_msg(value),
                edited_message=None, channel_post=None, edited_channel_post=None,
                inline_query=None, chosen_inline_result=None,
                callback_query=None, shipping_query=None,
                pre_checkout_query=None, poll=None, poll_answer=None,
                my_chat_member=None, chat_member=None, chat_join_request=None,
            )
            telegram_bot.process_new_updates([update])
        else:
            update = types.Update(
                update_id=1, message=None,
                edited_message=None, channel_post=None, edited_channel_post=None,
                inline_query=None, chosen_inline_result=None,
                callback_query=make_cb(value), shipping_query=None,
                pre_checkout_query=None, poll=None, poll_answer=None,
                my_chat_member=None, chat_member=None, chat_join_request=None,
            )
            telegram_bot.process_new_updates([update])
    except Exception as e:
        print(f"  ❌ {name:45s} EXCEPTION: {e}")
        return False

    send_count = sum(1 for r in responses if r["type"] in ("send", "photo", "edit"))
    if send_count > 0:
        preview = responses[0].get("text", "[photo/edit]")[:50]
        print(f"  ✅ {name:45s} → {send_count} msg(s): {preview}")
        return True
    else:
        print(f"  ❌ {name:45s} → NO RESPONSE SENT")
        return False

# Ensure user_data is initialized
if USER_ID not in tg_module.user_data:
    tg_module.user_data[USER_ID] = {}
tg_module.user_data[USER_ID]["step"] = ""

print("=" * 70)
print("DEEP HANDLER RESPONSE VERIFICATION")
print("=" * 70)

results = {"passed": 0, "failed": 0, "failures": []}

tests = [
    # Main menu
    ("📞 Phone Numbers", "message", "📞 Phone Numbers"),
    ("🎙 IVR Flows", "message", "🎙 IVR Flows"),
    ("☎️ Make a Call", "message", "☎️ Make a Call"),
    ("📋 Campaigns", "message", "📋 Campaigns"),
    ("📬 Inbox", "message", "📬 Inbox"),
    ("💰 Wallet & Billing", "message", "💰 Wallet & Billing"),
    ("Account 👤", "message", "Account 👤"),
    ("Help ℹ️", "message", "Help ℹ️"),
    # Phone hub inline
    ("buy_number", "callback", "buy_number"),
    ("my_numbers", "callback", "my_numbers"),
    ("sms_inbox", "callback", "sms_inbox"),
    ("phone_hub_back", "callback", "phone_hub_back"),
    # Inbox hub inline
    ("call_history", "callback", "call_history"),
    ("call_recordings", "callback", "call_recordings"),
    ("dtmf_responses_hub", "callback", "dtmf_responses_hub"),
    ("inbox_hub_back", "callback", "inbox_hub_back"),
    # Wallet inline
    ("top_up_wallet", "callback", "top_up_wallet"),
    ("transaction_history", "callback", "transaction_history"),
    ("view_subscription", "callback", "view_subscription"),
    ("update_subscription", "callback", "update_subscription"),
    ("wallet_hub_back", "callback", "wallet_hub_back"),
    ("check_wallet", "callback", "check_wallet"),
    # Navigation
    ("back_to_welcome_message", "callback", "back_to_welcome_message"),
    ("back_to_billing", "callback", "back_to_billing"),
    ("back_account", "callback", "back_account"),
    ("back_to_campaign_home", "callback", "back_to_campaign_home"),
    # Onboarding
    ("how_it_works", "callback", "how_it_works"),
    ("activate_free_plan", "callback", "activate_free_plan"),
    ("activate_subscription", "callback", "activate_subscription"),
    # Account sub
    ("Profile 👤", "message", "Profile 👤"),
    ("Settings ⚙", "message", "Settings ⚙"),
    ("Back ↩️", "message", "Back ↩️"),
    # IVR sub
    ("🤖 AI Assisted Flow", "message", "🤖 AI Assisted Flow"),
    ("🛠️ Advanced User Flow", "message", "🛠️ Advanced User Flow"),
    ("Single IVR Call 🟢", "message", "Single IVR Call 🟢"),
    ("Bulk IVR Call 🔵", "message", "Bulk IVR Call 🔵"),
    ("Call Status ℹ", "message", "Call Status ℹ"),
    # Campaign sub
    ("🗓️ Scheduled Campaigns", "message", "🗓️ Scheduled Campaigns"),
    ("🚀 Active Campaigns", "message", "🚀 Active Campaigns"),
    ("🏠 Return Home", "message", "🏠 Return Home"),
    # Plan flows
    ("change_language", "callback", "change_language"),
    ("help callback", "callback", "help"),
    ("view_terms", "callback", "view_terms"),
    # Number purchase
    ("buynum_US_local", "callback", "buynum_US_local"),
    ("buynum_US_tollfree", "callback", "buynum_US_tollfree"),
    ("buynum_CA_local", "callback", "buynum_CA_local"),
    ("buynum_back", "callback", "buynum_back"),
    # Billing sub-menus
    ("Billing & Subscription 📋", "message", "Billing & Subscription 📋"),
    ("Join Channel 📢", "message", "Join Channel 📢"),
    ("User Feedback 💬", "message", "User Feedback 💬"),
    ("Create IVR Flow 🆕", "message", "Create IVR Flow 🆕"),
    ("View Flows 📋", "message", "View Flows 📋"),
    ("Delete Flow 🗑", "message", "Delete Flow 🗑"),
    ("Top Up 💳", "message", "Top Up 💳"),
    ("DTMF Inbox 🔢", "message", "DTMF Inbox 🔢"),
    # Back buttons
    ("Back 📞", "message", "Back 📞"),
    ("Back 📲", "message", "Back 📲"),
    ("Back 👤", "message", "Back 👤"),
]

print(f"\nRunning {len(tests)} tests...\n")

for name, utype, value in tests:
    # Reset step between tests
    tg_module.user_data[USER_ID]["step"] = ""
    passed = test_handler(name, utype, value)
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
        results["failures"].append(name)

print("\n" + "=" * 70)
print(f"RESULTS: {results['passed']} PASSED | {results['failed']} FAILED")
print("=" * 70)
if results["failures"]:
    print("\nFAILED:")
    for f in results["failures"]:
        print(f"  ❌ {f}")

# Restore
telegram_bot.send_message = original_send
telegram_bot.send_photo = original_send_photo
telegram_bot.edit_message_text = original_edit
telegram_bot.answer_callback_query = original_answer
