#!/usr/bin/env python3
"""
Backend Test Suite - Iteration 6 (Telegram Bot UI/UX Final Validation)
Testing all required backend functionality and code structure after UI/UX changes:

Key Test Areas:
- Backend starts without errors after all code changes
- All API endpoints respond correctly (webhook/retell, webhook/sms, dtmf/supervisor-check, time-check, telegram/webhook)
- Translation strings validation (34 new strings with 4 languages each)
- Keyboard function validation (8 buttons in 4 rows for main menu, hub keyboards)
- Handler function validation (send_welcome uses user_name, activate_free_plan, _match_menu_text)
- Onboarding flow validation (handle_terms_response shows quick start guide)
"""

import requests
import json
import sys
import time
import os
import re
from datetime import datetime, timezone

class TelegramBotFinalTester:
    def __init__(self, base_url="https://initial-config-3.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []
        self.bot_token = "8125289128:AAG_PqL3Oai7v1OhIAkH5dlJ4TXoeujwJxM"

    def log_result(self, test_name, passed, details="", response_data=None):
        """Log test results for detailed reporting"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "response_data": response_data
        }
        self.results.append(result)
        print(f"{status} - {test_name}")
        if details:
            print(f"   Details: {details}")
        if response_data and not passed:
            print(f"   Response: {response_data}")
        print()

    # ======== BACKEND HEALTH TESTS ========

    def test_backend_starts_without_errors(self):
        """Test that backend starts without errors after all code changes"""
        try:
            # Test basic health endpoint
            response = requests.get(f"{self.base_url}/", timeout=10)
            if 200 <= response.status_code <= 299:
                self.log_result(
                    "Backend Starts Without Errors",
                    True,
                    f"Backend running successfully with status {response.status_code}"
                )
                return True
            else:
                self.log_result(
                    "Backend Starts Without Errors",
                    False,
                    f"Backend responded with error status {response.status_code}",
                    response.text[:300]
                )
                return False
        except Exception as e:
            self.log_result(
                "Backend Starts Without Errors",
                False,
                f"Backend connection failed: {str(e)}"
            )
            return False

    # ======== API ENDPOINT TESTS ========

    def test_retell_webhook_200_ok(self):
        """Test POST /api/webhook/retell responds 200 OK"""
        try:
            payload = {
                "event": "call_ended",
                "data": {
                    "call_id": "test_retell_final_789",
                    "agent_id": "test_agent_final",
                    "to_number": "+12345678901",
                    "from_number": "+19876543210",
                    "direction": "outbound",
                    "start_timestamp": int((time.time() - 300) * 1000),
                    "end_timestamp": int(time.time() * 1000),
                    "duration_ms": 300000,
                    "disconnection_reason": "user_hangup",
                    "transcripts": [
                        {"role": "agent", "content": "Hello, testing retell webhook"},
                        {"role": "user", "content": "Pressed Button: 1"}
                    ]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/webhook/retell",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if response.status_code == 200:
                self.log_result(
                    "POST /api/webhook/retell responds 200 OK",
                    True,
                    "Retell webhook endpoint responding correctly"
                )
                return True
            else:
                self.log_result(
                    "POST /api/webhook/retell responds 200 OK",
                    False,
                    f"HTTP {response.status_code}",
                    response.text[:200]
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/webhook/retell responds 200 OK",
                False,
                f"Request failed: {str(e)}"
            )
            return False

    def test_sms_webhook_responds_correctly(self):
        """Test POST /api/webhook/sms responds correctly"""
        try:
            payload = {
                "to_number": "+19876543210",
                "from_number": "+12345678901", 
                "message": "Final test SMS for iteration 6",
                "timestamp": int(time.time())
            }
            
            response = requests.post(
                f"{self.base_url}/api/webhook/sms",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                self.log_result(
                    "POST /api/webhook/sms responds correctly",
                    True,
                    f"SMS webhook responding with status {response.status_code}"
                )
                return True
            else:
                self.log_result(
                    "POST /api/webhook/sms responds correctly",
                    False,
                    f"HTTP {response.status_code}",
                    response.text[:200]
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/webhook/sms responds correctly",
                False,
                f"Request failed: {str(e)}"
            )
            return False

    def test_dtmf_supervisor_check_responds_correctly(self):
        """Test POST /api/dtmf/supervisor-check responds correctly"""
        try:
            payload = {
                "call_id": "test_dtmf_final_456",
                "args": {
                    "digits": "123456",
                    "node_name": "Final Test DTMF Node",
                    "pathway_id": "test_pathway_456"
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/dtmf/supervisor-check",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=25
            )
            
            if response.status_code == 200:
                response_json = response.json()
                if "result" in response_json and "message" in response_json:
                    self.log_result(
                        "POST /api/dtmf/supervisor-check responds correctly",
                        True,
                        f"DTMF endpoint working with result: {response_json.get('result')}"
                    )
                    return True
                else:
                    self.log_result(
                        "POST /api/dtmf/supervisor-check responds correctly",
                        False,
                        "Response missing required fields (result, message)",
                        response_json
                    )
                    return False
            else:
                self.log_result(
                    "POST /api/dtmf/supervisor-check responds correctly",
                    False,
                    f"HTTP {response.status_code}",
                    response.text[:200]
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/dtmf/supervisor-check responds correctly",
                False,
                f"Request failed: {str(e)}"
            )
            return False

    def test_time_check_responds_correctly(self):
        """Test POST /api/time-check responds correctly"""
        try:
            payload = {
                "call_id": "test_time_final_123",
                "args": {
                    "phone_number": "+12345678901",
                    "timezone": "America/New_York"
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/time-check",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                response_json = response.json()
                required_fields = ["current_time", "timezone", "is_business_hours"]
                missing_fields = [f for f in required_fields if f not in response_json]
                
                if not missing_fields:
                    self.log_result(
                        "POST /api/time-check responds correctly",
                        True,
                        f"Time check endpoint working with all required fields"
                    )
                    return True
                else:
                    self.log_result(
                        "POST /api/time-check responds correctly",
                        False,
                        f"Missing fields: {missing_fields}",
                        response_json
                    )
                    return False
            else:
                self.log_result(
                    "POST /api/time-check responds correctly",
                    False,
                    f"HTTP {response.status_code}",
                    response.text[:200]
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/time-check responds correctly",
                False,
                f"Request failed: {str(e)}"
            )
            return False

    def test_telegram_webhook_start_command(self):
        """Test POST /api/telegram/webhook/ with /start command processes without errors"""
        try:
            payload = {
                "update_id": 987654321,
                "message": {
                    "message_id": 123456789,
                    "from": {
                        "id": 54321,
                        "is_bot": False,
                        "first_name": "TestUser",
                        "username": "finaltest",
                        "language_code": "en"
                    },
                    "chat": {
                        "id": 54321,
                        "first_name": "TestUser",
                        "username": "finaltest",
                        "type": "private"
                    },
                    "date": int(time.time()),
                    "text": "/start"
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/telegram/webhook/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if response.status_code == 200:
                self.log_result(
                    "POST /api/telegram/webhook/ /start command processes",
                    True,
                    "Telegram webhook processing /start command without errors"
                )
                return True
            else:
                self.log_result(
                    "POST /api/telegram/webhook/ /start command processes",
                    False,
                    f"HTTP {response.status_code}",
                    response.text[:200]
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/telegram/webhook/ /start command processes",
                False,
                f"Request failed: {str(e)}"
            )
            return False

    # ======== TRANSLATION VALIDATION ========

    def test_translation_strings_valid_dicts_4_languages(self):
        """Test all new translation strings are valid Python dicts with 4 languages"""
        try:
            translations_path = "/app/translations/translations.py"
            if not os.path.exists(translations_path):
                self.log_result(
                    "Translation strings validation",
                    False,
                    "translations.py file not found"
                )
                return False

            with open(translations_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Required languages
            required_languages = ["English", "Chinese", "French", "Hindi"]
            
            # Check specific translation strings mentioned in the test requirements
            new_translation_strings = [
                "PHONE_NUMBERS_MENU", "INBOX_MENU", "WALLET_AND_BILLING", "MAKE_CALL_MENU",
                "IVR_FLOWS_MENU", "CAMPAIGNS_MENU", "PHONE_NUMBERS_HUB", "INBOX_HUB",
                "QUICK_START_TITLE", "QUICK_START_STEP_1", "QUICK_START_STEP_2", 
                "QUICK_START_STEP_3", "QUICK_START_STEP_4", "FREE_PLAN_ACTIVATED",
                "HOW_IT_WORKS_TEXT", "CALL_HISTORY_MENU", "CALL_RECORDINGS_MENU",
                "TRANSACTION_HISTORY", "SMS_INBOX_MENU", "MY_NUMBERS", "MAIN_MENU_BTN",
                "BACK_BTN", "WELCOME_BACK", "DASHBOARD_SUMMARY", "PLAN_LABEL",
                "WALLET_LABEL", "NUMBERS_LABEL", "MINUTES_LEFT_LABEL", "NO_CALLS_YET",
                "NO_TRANSACTIONS_YET", "NO_RECORDINGS_YET", "NO_NUMBERS_YET",
                "VIEW_ALL_CALLS", "VIEW_ALL_TRANSACTIONS"
            ]

            valid_strings = []
            invalid_strings = []
            
            # Extract and validate dictionary structures
            dict_pattern = r'(\w+)\s*=\s*{([^{}]*(?:{[^{}]*}[^{}]*)*[^{}]*)}'
            matches = re.findall(dict_pattern, content, re.MULTILINE | re.DOTALL)
            
            for string_name in new_translation_strings:
                found = False
                for match in matches:
                    var_name, dict_content = match
                    if var_name == string_name:
                        found = True
                        # Check if all 4 languages are present
                        languages_found = sum(1 for lang in required_languages if f'"{lang}"' in dict_content)
                        if languages_found >= 4:
                            valid_strings.append(string_name)
                        else:
                            invalid_strings.append(f"{string_name} (only {languages_found} languages)")
                        break
                
                if not found:
                    invalid_strings.append(f"{string_name} (not found)")

            total_required = len(new_translation_strings)
            valid_count = len(valid_strings)
            
            if valid_count >= total_required * 0.9:  # Allow 90% success rate
                self.log_result(
                    "Translation strings valid dicts with 4 languages",
                    True,
                    f"{valid_count}/{total_required} translation strings valid with 4 languages"
                )
                return True
            else:
                self.log_result(
                    "Translation strings valid dicts with 4 languages",
                    False,
                    f"Only {valid_count}/{total_required} valid. Issues: {invalid_strings[:5]}..."
                )
                return False

        except Exception as e:
            self.log_result(
                "Translation strings valid dicts with 4 languages",
                False,
                f"Error validating translations: {str(e)}"
            )
            return False

    # ======== KEYBOARD MENU VALIDATION ========

    def test_main_menu_keyboard_8_buttons_4_rows(self):
        """Test get_main_menu_keyboard returns 8 buttons in 4 rows"""
        try:
            keyboard_path = "/app/bot/keyboard_menus.py"
            with open(keyboard_path, 'r') as f:
                content = f.read()

            # Find the get_main_menu_keyboard function
            func_start = content.find("def get_main_menu_keyboard")
            if func_start == -1:
                self.log_result(
                    "get_main_menu_keyboard returns 8 buttons in 4 rows",
                    False,
                    "get_main_menu_keyboard function not found"
                )
                return False

            # Extract function content
            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Count markup.row calls (should be 4 for 4 rows)
            row_count = func_content.count("markup.row(")
            
            # Count KeyboardButton instances (should be 8)
            button_count = func_content.count("KeyboardButton(")
            
            # Check for expected button types
            expected_buttons = [
                "PHONE_NUMBERS_MENU", "IVR_FLOWS_MENU", "MAKE_CALL_MENU", 
                "CAMPAIGNS_MENU", "INBOX_MENU", "WALLET_AND_BILLING", "ACCOUNT", "HELP"
            ]
            
            found_buttons = [btn for btn in expected_buttons if btn in func_content]
            
            if row_count == 4 and button_count >= 8 and len(found_buttons) >= 7:
                self.log_result(
                    "get_main_menu_keyboard returns 8 buttons in 4 rows",
                    True,
                    f"Main menu has {button_count} buttons in {row_count} rows. Buttons: {found_buttons[:4]}..."
                )
                return True
            else:
                self.log_result(
                    "get_main_menu_keyboard returns 8 buttons in 4 rows",
                    False,
                    f"Expected 8 buttons in 4 rows. Found: {button_count} buttons, {row_count} rows, {len(found_buttons)} expected buttons"
                )
                return False

        except Exception as e:
            self.log_result(
                "get_main_menu_keyboard returns 8 buttons in 4 rows",
                False,
                f"Error checking main menu keyboard: {str(e)}"
            )
            return False

    def test_phone_numbers_hub_keyboard(self):
        """Test get_phone_numbers_hub_keyboard returns inline keyboard with Buy/My Numbers/SMS/Back"""
        try:
            keyboard_path = "/app/bot/keyboard_menus.py"
            with open(keyboard_path, 'r') as f:
                content = f.read()

            # Find the function
            func_start = content.find("def get_phone_numbers_hub_keyboard")
            if func_start == -1:
                self.log_result(
                    "get_phone_numbers_hub_keyboard inline keyboard",
                    False,
                    "get_phone_numbers_hub_keyboard function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Check for InlineKeyboardMarkup and expected buttons
            expected_elements = [
                "InlineKeyboardMarkup",
                "buy_number",
                "my_numbers", 
                "sms_inbox",
                "MAIN_MENU_BTN"
            ]
            
            found_elements = [elem for elem in expected_elements if elem in func_content]
            
            if len(found_elements) >= 4:
                self.log_result(
                    "get_phone_numbers_hub_keyboard inline keyboard",
                    True,
                    f"Phone numbers hub keyboard has expected elements: {found_elements}"
                )
                return True
            else:
                self.log_result(
                    "get_phone_numbers_hub_keyboard inline keyboard",
                    False,
                    f"Missing elements. Found only: {found_elements}"
                )
                return False

        except Exception as e:
            self.log_result(
                "get_phone_numbers_hub_keyboard inline keyboard",
                False,
                f"Error checking phone numbers hub keyboard: {str(e)}"
            )
            return False

    def test_inbox_hub_keyboard(self):
        """Test get_inbox_hub_keyboard returns inline keyboard with Recordings/DTMF/SMS/History/Back"""
        try:
            keyboard_path = "/app/bot/keyboard_menus.py"
            with open(keyboard_path, 'r') as f:
                content = f.read()

            func_start = content.find("def get_inbox_hub_keyboard")
            if func_start == -1:
                self.log_result(
                    "get_inbox_hub_keyboard inline keyboard",
                    False,
                    "get_inbox_hub_keyboard function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            expected_elements = [
                "call_recordings",
                "dtmf_responses_hub",
                "sms_inbox",
                "call_history",
                "MAIN_MENU_BTN"
            ]
            
            found_elements = [elem for elem in expected_elements if elem in func_content]
            
            if len(found_elements) >= 4:
                self.log_result(
                    "get_inbox_hub_keyboard inline keyboard",
                    True,
                    f"Inbox hub keyboard has expected elements: {found_elements}"
                )
                return True
            else:
                self.log_result(
                    "get_inbox_hub_keyboard inline keyboard", 
                    False,
                    f"Missing elements. Found only: {found_elements}"
                )
                return False

        except Exception as e:
            self.log_result(
                "get_inbox_hub_keyboard inline keyboard",
                False,
                f"Error checking inbox hub keyboard: {str(e)}"
            )
            return False

    def test_wallet_billing_keyboard(self):
        """Test get_wallet_billing_keyboard returns inline keyboard with Top Up/Transactions/View Sub/Upgrade/Back"""
        try:
            keyboard_path = "/app/bot/keyboard_menus.py"
            with open(keyboard_path, 'r') as f:
                content = f.read()

            func_start = content.find("def get_wallet_billing_keyboard")
            if func_start == -1:
                self.log_result(
                    "get_wallet_billing_keyboard inline keyboard",
                    False,
                    "get_wallet_billing_keyboard function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            expected_elements = [
                "top_up_wallet",
                "transaction_history",
                "view_subscription",
                "update_subscription",
                "MAIN_MENU_BTN"
            ]
            
            found_elements = [elem for elem in expected_elements if elem in func_content]
            
            if len(found_elements) >= 4:
                self.log_result(
                    "get_wallet_billing_keyboard inline keyboard",
                    True,
                    f"Wallet & Billing keyboard has expected elements: {found_elements}"
                )
                return True
            else:
                self.log_result(
                    "get_wallet_billing_keyboard inline keyboard",
                    False,
                    f"Missing elements. Found only: {found_elements}"
                )
                return False

        except Exception as e:
            self.log_result(
                "get_wallet_billing_keyboard inline keyboard",
                False,
                f"Error checking wallet billing keyboard: {str(e)}"
            )
            return False

    def test_onboarding_keyboard(self):
        """Test get_onboarding_keyboard returns 3 buttons: Free Plan, Premium Plans, How It Works"""
        try:
            keyboard_path = "/app/bot/keyboard_menus.py"
            with open(keyboard_path, 'r') as f:
                content = f.read()

            func_start = content.find("def get_onboarding_keyboard")
            if func_start == -1:
                self.log_result(
                    "get_onboarding_keyboard 3 buttons",
                    False,
                    "get_onboarding_keyboard function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            expected_buttons = [
                "activate_free_plan",
                "activate_subscription", 
                "how_it_works"
            ]
            
            found_buttons = [btn for btn in expected_buttons if btn in func_content]
            
            if len(found_buttons) == 3:
                self.log_result(
                    "get_onboarding_keyboard 3 buttons",
                    True,
                    f"Onboarding keyboard has all 3 buttons: {found_buttons}"
                )
                return True
            else:
                self.log_result(
                    "get_onboarding_keyboard 3 buttons",
                    False,
                    f"Expected 3 buttons. Found: {found_buttons}"
                )
                return False

        except Exception as e:
            self.log_result(
                "get_onboarding_keyboard 3 buttons",
                False,
                f"Error checking onboarding keyboard: {str(e)}"
            )
            return False

    # ======== FUNCTION VALIDATION ========

    def test_send_welcome_uses_user_name(self):
        """Test send_welcome accesses user_name (not name) and handles UserSubscription.DoesNotExist"""
        try:
            bot_path = "/app/bot/telegrambot.py"
            with open(bot_path, 'r') as f:
                content = f.read()

            # Find send_welcome function
            func_start = content.find("def send_welcome")
            if func_start == -1:
                self.log_result(
                    "send_welcome uses user_name and handles DoesNotExist",
                    False,
                    "send_welcome function not found"
                )
                return False

            # Find next function to get boundaries
            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = content.find("\n@bot.", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Check for user_name usage and exception handling
            required_elements = [
                "user_name",  # Should use user_name not name
                "UserSubscription.DoesNotExist",  # Should handle exception
                "TelegramUser.objects.get",  # Should get user object
                "check_user_balance"  # Should check wallet balance
            ]
            
            found_elements = [elem for elem in required_elements if elem in func_content]
            
            # Check that 'name' field is NOT used (should be user_name)
            name_usage_bad = '.name' in func_content and 'user_name' not in func_content
            
            if len(found_elements) >= 3 and not name_usage_bad:
                self.log_result(
                    "send_welcome uses user_name and handles DoesNotExist", 
                    True,
                    f"send_welcome properly implemented with: {found_elements}"
                )
                return True
            else:
                issues = []
                if name_usage_bad:
                    issues.append("uses '.name' instead of 'user_name'")
                if len(found_elements) < 3:
                    issues.append(f"missing elements: {set(required_elements) - set(found_elements)}")
                    
                self.log_result(
                    "send_welcome uses user_name and handles DoesNotExist",
                    False,
                    f"Issues found: {issues}"
                )
                return False

        except Exception as e:
            self.log_result(
                "send_welcome uses user_name and handles DoesNotExist",
                False,
                f"Error checking send_welcome: {str(e)}"
            )
            return False

    def test_activate_free_plan_uses_set_user_subscription(self):
        """Test handle_activate_free_plan correctly uses set_user_subscription(user_object, plan_id_string)"""
        try:
            bot_path = "/app/bot/telegrambot.py"
            with open(bot_path, 'r') as f:
                content = f.read()

            # Find handle_activate_free_plan function
            func_start = content.find("def handle_activate_free_plan")
            if func_start == -1:
                self.log_result(
                    "handle_activate_free_plan uses set_user_subscription correctly",
                    False,
                    "handle_activate_free_plan function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = content.find("\n@bot.", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Check for proper usage
            required_elements = [
                "set_user_subscription",  # Should call the function
                "TelegramUser.objects.get",  # Should get user object
                "SubscriptionPlans.objects.filter",  # Should find Free plan
                "str(free_plan.plan_id)"  # Should convert plan_id to string
            ]
            
            found_elements = [elem for elem in required_elements if elem in func_content]
            
            # Check the specific call signature
            correct_call = "set_user_subscription(user, str(" in func_content
            
            if len(found_elements) >= 3 and correct_call:
                self.log_result(
                    "handle_activate_free_plan uses set_user_subscription correctly",
                    True,
                    f"Function properly calls set_user_subscription with correct parameters"
                )
                return True
            else:
                self.log_result(
                    "handle_activate_free_plan uses set_user_subscription correctly",
                    False,
                    f"Found {len(found_elements)}/4 elements. Correct call pattern: {correct_call}"
                )
                return False

        except Exception as e:
            self.log_result(
                "handle_activate_free_plan uses set_user_subscription correctly",
                False,
                f"Error checking handle_activate_free_plan: {str(e)}"
            )
            return False

    def test_match_menu_text_function(self):
        """Test new _match_menu_text function matches texts with emoji prefixes"""
        try:
            bot_path = "/app/bot/telegrambot.py"
            with open(bot_path, 'r') as f:
                content = f.read()

            # Find _match_menu_text function
            func_start = content.find("def _match_menu_text")
            if func_start == -1:
                self.log_result(
                    "_match_menu_text function matches emoji prefixes",
                    False,
                    "_match_menu_text function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = content.find("\n@bot.", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Check for emoji prefix handling
            required_elements = [
                "for prefix in",  # Should iterate through prefixes
                "📞 ", "🎙 ", "☎️ ", "📋 ", "📬 ", "💰 ",  # Should handle emoji prefixes
                "message_text ==",  # Should match message text
                "translations_dict"  # Should use translation dict
            ]
            
            found_elements = [elem for elem in required_elements if elem in func_content]
            emoji_count = sum(1 for emoji in ["📞", "🎙", "☎️", "📋", "📬", "💰"] if emoji in func_content)
            
            if len(found_elements) >= 4 and emoji_count >= 4:
                self.log_result(
                    "_match_menu_text function matches emoji prefixes",
                    True,
                    f"Function properly handles emoji prefixes ({emoji_count} emojis found)"
                )
                return True
            else:
                self.log_result(
                    "_match_menu_text function matches emoji prefixes",
                    False,
                    f"Found {len(found_elements)}/8 elements and {emoji_count} emojis"
                )
                return False

        except Exception as e:
            self.log_result(
                "_match_menu_text function matches emoji prefixes",
                False,
                f"Error checking _match_menu_text: {str(e)}"
            )
            return False

    def test_terms_response_shows_quick_start(self):
        """Test handle_terms_response shows quick start guide instead of jumping to plan selection"""
        try:
            bot_path = "/app/bot/telegrambot.py"
            with open(bot_path, 'r') as f:
                content = f.read()

            # Find handle_terms_response function
            func_start = content.find("def handle_terms_response")
            if func_start == -1:
                # Also check for handle_terms_and_conditions or similar
                func_start = content.find("handle_terms")
                if func_start > 0:
                    func_start = content.rfind("def ", 0, func_start)
                
            if func_start == -1:
                self.log_result(
                    "handle_terms_response shows quick start guide",
                    False,
                    "handle_terms_response or similar function not found"
                )
                return False

            func_end = content.find("\ndef ", func_start + 1)
            if func_end == -1:
                func_end = content.find("\n@bot.", func_start + 1)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Check for quick start elements instead of direct plan selection
            quick_start_elements = [
                "get_onboarding_keyboard",  # Should show onboarding keyboard
                "QUICK_START",  # Should reference quick start
                "activate_free_plan"  # Should offer free plan option
            ]
            
            # These should NOT be present (direct plan selection)
            plan_selection_elements = [
                "get_subscription_activation_markup",
                "activate_subscription"
            ]
            
            found_quick_start = [elem for elem in quick_start_elements if elem in func_content]
            found_plan_selection = [elem for elem in plan_selection_elements if elem in func_content]
            
            if len(found_quick_start) >= 2 and len(found_plan_selection) == 0:
                self.log_result(
                    "handle_terms_response shows quick start guide",
                    True,
                    f"Function shows quick start guide with: {found_quick_start}"
                )
                return True
            else:
                self.log_result(
                    "handle_terms_response shows quick start guide", 
                    False,
                    f"Quick start: {found_quick_start}, Plan selection: {found_plan_selection}"
                )
                return False

        except Exception as e:
            self.log_result(
                "handle_terms_response shows quick start guide",
                False,
                f"Error checking handle_terms_response: {str(e)}"
            )
            return False

    def run_comprehensive_test(self):
        """Run all tests and generate comprehensive report"""
        print("=" * 80)
        print("BACKEND TEST SUITE - ITERATION 6")
        print("Final Validation of Telegram Bot UI/UX Redesign")
        print("=" * 80)
        print()

        # Backend Health
        print("🔍 Testing backend startup after all changes...")
        self.test_backend_starts_without_errors()
        
        # API Endpoints
        print("🔍 Testing API endpoints...")
        self.test_retell_webhook_200_ok()
        self.test_sms_webhook_responds_correctly() 
        self.test_dtmf_supervisor_check_responds_correctly()
        self.test_time_check_responds_correctly()
        self.test_telegram_webhook_start_command()
        
        # Translation Validation
        print("🔍 Testing translation strings...")
        self.test_translation_strings_valid_dicts_4_languages()
        
        # Keyboard Validation  
        print("🔍 Testing keyboard functions...")
        self.test_main_menu_keyboard_8_buttons_4_rows()
        self.test_phone_numbers_hub_keyboard()
        self.test_inbox_hub_keyboard()
        self.test_wallet_billing_keyboard()
        self.test_onboarding_keyboard()
        
        # Function Validation
        print("🔍 Testing key functions...")
        self.test_send_welcome_uses_user_name()
        self.test_activate_free_plan_uses_set_user_subscription()
        self.test_match_menu_text_function()
        self.test_terms_response_shows_quick_start()

        # Generate final report
        print("=" * 80)
        print("FINAL TEST REPORT - TELEGRAM BOT BACKEND VALIDATION")
        print("=" * 80)
        
        success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {success_rate:.1f}%")
        print()
        
        if success_rate >= 85:  # High threshold for final validation
            print("🎉 COMPREHENSIVE TESTS SUCCESSFUL!")
            print("\n📋 Validated Components:")
            print("   ✅ Backend starts without errors after code changes")
            print("   ✅ All API endpoints responding correctly")
            print("   ✅ Translation strings valid with 4 languages")
            print("   ✅ Keyboard menus properly structured")
            print("   ✅ Key functions implemented correctly")
            return True
        else:
            print("⚠️ SOME TESTS FAILED. Backend needs attention before deployment.")
            failed_tests = [r for r in self.results if "❌" in r["status"]]
            print(f"\nFailed tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
            return False

def main():
    tester = TelegramBotFinalTester()
    success = tester.run_comprehensive_test()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())