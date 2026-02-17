"""
End-to-end webhook simulation: sends fake updates to the webhook endpoint
and monitors backend logs for errors.
"""
import os, sys, json, time, subprocess, requests

POD_URL = "http://localhost:8001"
USER_ID = 5590563715
BOT_ID = 8125289128
update_counter = 200000000

def clear_logs():
    """Clear backend logs to isolate errors per test."""
    subprocess.run(["truncate", "-s", "0", "/var/log/supervisor/backend.err.log"], capture_output=True)
    subprocess.run(["truncate", "-s", "0", "/var/log/supervisor/backend.out.log"], capture_output=True)

def get_errors():
    """Get errors from backend logs."""
    try:
        err = open("/var/log/supervisor/backend.err.log").read()
        out = open("/var/log/supervisor/backend.out.log").read()
        # Filter for actual errors (not INFO/WARNING messages)
        error_lines = []
        for line in (err + out).split("\n"):
            lower = line.lower()
            if any(kw in lower for kw in ["error", "exception", "traceback", "does not exist", "keyerror", "typeerror", "attributeerror", "valueerror"]):
                error_lines.append(line.strip())
        return error_lines
    except:
        return []

def send_message(text):
    """Simulate a text message from user."""
    global update_counter
    update_counter += 1
    payload = {
        "update_id": update_counter,
        "message": {
            "message_id": update_counter,
            "from": {"id": USER_ID, "is_bot": False, "first_name": "Ray"},
            "chat": {"id": USER_ID, "type": "private"},
            "date": int(time.time()),
            "text": text
        }
    }
    try:
        r = requests.post(f"{POD_URL}/api/telegram/webhook/", json=payload, timeout=15)
        return r.status_code
    except Exception as e:
        return f"REQ_ERROR: {e}"

def send_callback(data):
    """Simulate a callback query (inline button press)."""
    global update_counter
    update_counter += 1
    payload = {
        "update_id": update_counter,
        "callback_query": {
            "id": str(update_counter),
            "from": {"id": USER_ID, "is_bot": False, "first_name": "Ray"},
            "message": {
                "message_id": update_counter - 1,
                "from": {"id": BOT_ID, "is_bot": True, "first_name": "SpeechcueBot"},
                "chat": {"id": USER_ID, "type": "private"},
                "date": int(time.time()),
                "text": "Previous message"
            },
            "chat_instance": "test",
            "data": data
        }
    }
    try:
        r = requests.post(f"{POD_URL}/api/telegram/webhook/", json=payload, timeout=15)
        return r.status_code
    except Exception as e:
        return f"REQ_ERROR: {e}"

results = []

def test(name, func, *args):
    clear_logs()
    time.sleep(0.3)
    status = func(*args)
    time.sleep(1.0)  # Wait for async processing
    errors = get_errors()
    passed = len(errors) == 0 and status == 200
    results.append((name, passed, errors[:3], status))
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name:45s} HTTP={status}")
    if errors:
        for e in errors[:3]:
            print(f"     ERROR: {e[:150]}")

print("=" * 70)
print("WEBHOOK END-TO-END BUTTON TESTS")
print("=" * 70)

# === MAIN MENU BUTTONS ===
print("\n--- MAIN MENU (Reply Keyboard) ---")
test("📞 Phone Numbers", send_message, "📞 Phone Numbers")
test("🎙 IVR Flows", send_message, "🎙 IVR Flows")
test("☎️ Make a Call", send_message, "☎️ Make a Call")
test("📋 Campaigns", send_message, "📋 Campaigns")
test("📬 Inbox", send_message, "📬 Inbox")
test("💰 Wallet & Billing", send_message, "💰 Wallet & Billing")
test("Account 👤", send_message, "Account 👤")
test("Help ℹ️", send_message, "Help ℹ️")

# === PHONE NUMBERS HUB CALLBACKS ===
print("\n--- PHONE NUMBERS HUB (Inline) ---")
test("Buy Number", send_callback, "buy_number")
test("My Numbers", send_callback, "my_numbers")
test("SMS Inbox", send_callback, "sms_inbox")
test("Phone Hub Back", send_callback, "phone_hub_back")

# === INBOX HUB CALLBACKS ===
print("\n--- INBOX HUB (Inline) ---")
test("Call History", send_callback, "call_history")
test("Call Recordings", send_callback, "call_recordings")
test("DTMF Responses Hub", send_callback, "dtmf_responses_hub")
test("Inbox Hub Back", send_callback, "inbox_hub_back")

# === WALLET & BILLING CALLBACKS ===
print("\n--- WALLET & BILLING (Inline) ---")
test("Top Up Wallet", send_callback, "top_up_wallet")
test("Transaction History", send_callback, "transaction_history")
test("View Subscription", send_callback, "view_subscription")
test("Update Subscription", send_callback, "update_subscription")
test("Wallet Hub Back", send_callback, "wallet_hub_back")
test("Check Wallet", send_callback, "check_wallet")

# === NAVIGATION ===
print("\n--- NAVIGATION (Inline) ---")
test("Back to Welcome", send_callback, "back_to_welcome_message")
test("Back to Billing", send_callback, "back_to_billing")
test("Back Account", send_callback, "back_account")
test("Back to Campaign Home", send_callback, "back_to_campaign_home")

# === ONBOARDING ===
print("\n--- ONBOARDING (Inline) ---")
test("How It Works", send_callback, "how_it_works")
test("Activate Free Plan", send_callback, "activate_free_plan")

# === ACCOUNT SUB-MENU ===
print("\n--- ACCOUNT SUB-MENU ---")
test("Profile 👤", send_message, "Profile 👤")
test("Settings ⚙", send_message, "Settings ⚙")
test("Back ↩️", send_message, "Back ↩️")

# === IVR SUB-MENUS ===
print("\n--- IVR SUB-MENUS ---")
test("🤖 AI Assisted Flow", send_message, "🤖 AI Assisted Flow")
test("🛠️ Advanced User Flow", send_message, "🛠️ Advanced User Flow")
test("Single IVR Call 🟢", send_message, "Single IVR Call 🟢")
test("Bulk IVR Call 🔵", send_message, "Bulk IVR Call 🔵")
test("Call Status ℹ", send_message, "Call Status ℹ")

# === CAMPAIGN SUB-MENUS ===
print("\n--- CAMPAIGN SUB-MENUS ---")
test("🗓️ Scheduled Campaigns", send_message, "🗓️ Scheduled Campaigns")
test("🚀 Active Campaigns", send_message, "🚀 Active Campaigns")
test("🏠 Return Home", send_message, "🏠 Return Home")

# === PLAN FLOWS ===
print("\n--- PLAN FLOWS (Inline) ---")
test("Change Language", send_callback, "change_language")
test("Help (callback)", send_callback, "help")
test("View Terms", send_callback, "view_terms")
test("Activate Subscription", send_callback, "activate_subscription")

# === NUMBER PURCHASE ===
print("\n--- NUMBER PURCHASE (Inline) ---")
test("Buy US Local", send_callback, "buynum_US_local")
test("Buy US Toll-Free", send_callback, "buynum_US_tollfree")
test("Buy CA Local", send_callback, "buynum_CA_local")
test("Buy Num Back", send_callback, "buynum_back")

# === SUMMARY ===
print("\n" + "=" * 70)
passed = sum(1 for _, p, _, _ in results if p)
failed = sum(1 for _, p, _, _ in results if not p)
print(f"TOTAL: {len(results)} tests | ✅ {passed} passed | ❌ {failed} failed")
print("=" * 70)

if failed:
    print("\nFAILED TESTS:")
    for name, p, errors, status in results:
        if not p:
            print(f"\n  ❌ {name} (HTTP {status})")
            for e in errors:
                print(f"     {e[:200]}")

# Write results to file
with open("/app/test_reports/button_audit.json", "w") as f:
    json.dump({
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "details": [{"name": n, "passed": p, "errors": e, "status": s} for n, p, e, s in results]
    }, f, indent=2)
print("\nResults saved to /app/test_reports/button_audit.json")
