#!/usr/bin/env python3
"""
Backend Testing for Speechcue Telegram Bot Django Application
Tests all API endpoints and integrations
"""
import requests
import sys
import json
import os
from datetime import datetime

class SpeechcueBackendTester:
    def __init__(self, base_url="https://quickstart-43.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.passed_tests = []
        self.critical_issues = []
        
    def run_test(self, name, method, endpoint, expected_status=200, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                self.passed_tests.append(name)
                print(f"✅ PASS - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {response_data}")
                    return True, response_data
                except:
                    print(f"   Response (text): {response.text}")
                    return True, response.text
            else:
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "response": response.text[:200],
                    "url": url
                })
                if response.status_code in [500, 404]:
                    self.critical_issues.append(f"{name}: HTTP {response.status_code}")
                print(f"❌ FAIL - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False, response.text
                
        except requests.exceptions.Timeout:
            self.failed_tests.append({
                "test": name,
                "error": "Timeout after 10 seconds",
                "url": url
            })
            print(f"❌ FAIL - Timeout after 10 seconds")
            return False, "timeout"
            
        except Exception as e:
            self.failed_tests.append({
                "test": name,
                "error": str(e),
                "url": url
            })
            print(f"❌ FAIL - Error: {str(e)}")
            return False, str(e)

    def test_telegram_webhook(self):
        """Test Telegram webhook endpoint"""
        test_data = {
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": "/start"
            }
        }
        
        return self.run_test(
            "Telegram Webhook",
            "POST", 
            "/api/telegram/webhook/",
            expected_status=200,
            data=test_data
        )

    def test_retell_webhook(self):
        """Test Retell AI webhook endpoint"""
        test_data = {
            "event": "call_started",
            "data": {
                "call_id": "test_call_123",
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "direction": "outbound",
                "agent_id": "test_agent"
            }
        }
        
        return self.run_test(
            "Retell Webhook",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=test_data
        )

    def test_dtmf_supervisor_check(self):
        """Test DTMF supervisor check endpoint"""
        test_data = {
            "call_id": "test_call_dtmf_123",
            "args": {
                "digits": "1234",
                "node_name": "PIN Entry Test"
            }
        }
        
        return self.run_test(
            "DTMF Supervisor Check",
            "POST",
            "/api/dtmf/supervisor-check",
            expected_status=200,
            data=test_data
        )

    def test_sms_webhook(self):
        """Test SMS webhook endpoint"""
        test_data = {
            "to_number": "+1234567890",
            "from_number": "+1987654321",
            "message": "Test SMS message"
        }
        
        return self.run_test(
            "SMS Webhook",
            "POST",
            "/api/webhook/sms",
            expected_status=200,
            data=test_data
        )

    def test_time_check(self):
        """Test time check endpoint"""
        test_data = {
            "call_id": "test_call_time_123",
            "args": {
                "phone_number": "+1234567890"
            }
        }
        
        return self.run_test(
            "Time Check",
            "POST",
            "/api/time-check",
            expected_status=200,
            data=test_data
        )

    def test_get_endpoints(self):
        """Test GET endpoints that might exist"""
        endpoints = [
            ("/admin/", 200),  # Django admin might redirect but should respond
        ]
        
        for endpoint, expected_status in endpoints:
            self.run_test(
                f"GET {endpoint}",
                "GET",
                endpoint,
                expected_status=expected_status
            )

    def test_server_health(self):
        """Test basic server health"""
        # Test root endpoint
        self.run_test(
            "Server Root",
            "GET",
            "/",
            expected_status=200  # or 404, depending on Django setup
        )

    def check_environment_variables(self):
        """Check if critical environment variables are set"""
        print("\n🔍 Checking Environment Variables...")
        
        # Read from .env file
        env_vars = {}
        try:
            with open('/app/.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value
        except Exception as e:
            print(f"❌ Could not read .env file: {e}")
            return False
        
        required_vars = [
            'API_TOKEN',
            'RETELL_API_KEY', 
            'POSTGRES_DB',
            'REDIS_URL',
            'webhook_url',
            'DYNOPAY_API_KEY',
            'DYNOPAY_WALLET_TOKEN'
        ]
        
        all_present = True
        for var in required_vars:
            if var in env_vars and env_vars[var]:
                print(f"✅ {var}: {'*' * 20}...{env_vars[var][-10:]}")
            else:
                print(f"❌ {var}: Missing or empty")
                all_present = False
                
        return all_present

    def check_database_connection(self):
        """Check if PostgreSQL connection string is valid"""
        print("\n🔍 Checking Database Configuration...")
        
        try:
            with open('/app/.env', 'r') as f:
                content = f.read()
                if 'postgresql://' in content and 'nozomi.proxy.rlwy.net:19535' in content:
                    print("✅ PostgreSQL connection string found and looks valid")
                    return True
                else:
                    print("❌ PostgreSQL connection string not found or invalid")
                    return False
        except Exception as e:
            print(f"❌ Could not check database config: {e}")
            return False

    def check_redis_connection(self):
        """Check if Redis connection string is valid"""
        print("\n🔍 Checking Redis Configuration...")
        
        try:
            with open('/app/.env', 'r') as f:
                content = f.read()
                if 'redis://' in content and 'metro.proxy.rlwy.net:40681' in content:
                    print("✅ Redis connection string found and looks valid")
                    return True
                else:
                    print("❌ Redis connection string not found or invalid")
                    return False
        except Exception as e:
            print(f"❌ Could not check Redis config: {e}")
            return False

    def check_webhook_configuration(self):
        """Check if webhook URL is correctly set"""
        print("\n🔍 Checking Webhook Configuration...")
        
        try:
            with open('/app/.env', 'r') as f:
                content = f.read()
                expected_url = "https://quickstart-43.preview.emergentagent.com"
                if expected_url in content:
                    print(f"✅ Webhook URL correctly set to: {expected_url}")
                    return True
                else:
                    print(f"❌ Webhook URL not set to expected value: {expected_url}")
                    return False
        except Exception as e:
            print(f"❌ Could not check webhook config: {e}")
            return False

    def print_summary(self):
        """Print test results summary"""
        print(f"\n" + "="*60)
        print(f"📊 TEST SUMMARY")
        print(f"="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {len(self.failed_tests)}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "N/A")
        
        if self.passed_tests:
            print(f"\n✅ PASSED TESTS:")
            for test in self.passed_tests:
                print(f"   • {test}")
        
        if self.failed_tests:
            print(f"\n❌ FAILED TESTS:")
            for test in self.failed_tests:
                print(f"   • {test['test']}")
                if 'expected' in test:
                    print(f"     Expected: {test['expected']}, Got: {test['actual']}")
                if 'error' in test:
                    print(f"     Error: {test['error']}")
        
        if self.critical_issues:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in self.critical_issues:
                print(f"   • {issue}")
        
        return len(self.failed_tests) == 0

def main():
    print("🚀 Starting Speechcue Backend Testing...")
    print(f"Target URL: https://quickstart-43.preview.emergentagent.com")
    print("="*60)
    
    tester = SpeechcueBackendTester()
    
    # Environment and configuration checks
    env_ok = tester.check_environment_variables()
    db_ok = tester.check_database_connection()
    redis_ok = tester.check_redis_connection()
    webhook_ok = tester.check_webhook_configuration()
    
    # API endpoint tests
    print(f"\n" + "="*60)
    print("🧪 RUNNING API ENDPOINT TESTS")
    print("="*60)
    
    # Test all webhook endpoints
    tester.test_telegram_webhook()
    tester.test_retell_webhook()
    tester.test_dtmf_supervisor_check()
    tester.test_sms_webhook()
    tester.test_time_check()
    
    # Test other endpoints
    tester.test_server_health()
    tester.test_get_endpoints()
    
    # Print results
    success = tester.print_summary()
    
    # Overall health check
    print(f"\n" + "="*60)
    print("🏥 OVERALL SYSTEM HEALTH")
    print("="*60)
    
    config_score = sum([env_ok, db_ok, redis_ok, webhook_ok])
    api_score = tester.tests_passed
    
    print(f"Configuration Health: {config_score}/4")
    print(f"API Health: {api_score}/{tester.tests_run}")
    
    overall_health = "HEALTHY" if (config_score >= 3 and api_score >= tester.tests_run * 0.7) else "UNHEALTHY"
    print(f"Overall Status: {overall_health}")
    
    return 0 if success and config_score >= 3 else 1

if __name__ == "__main__":
    sys.exit(main())