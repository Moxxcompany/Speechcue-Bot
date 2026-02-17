#!/usr/bin/env python3
"""
Backend Testing for Call Outcome Tracking and Recording Features
Tests the new recording functionality and call outcome summary features
"""
import requests
import sys
import json
import os
import uuid
from datetime import datetime

class RecordingFeaturesTester:
    def __init__(self, base_url="https://quickstart-43.preview.emergentagent.com"):
        self.base_url = base_url
        self.test_user_id = 5590563715
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
                    if 'application/json' in response.headers.get('content-type', ''):
                        response_data = response.json()
                        print(f"   Response: {response_data}")
                        return True, response_data
                    else:
                        print(f"   Response (text): {response.text[:200]}")
                        return True, response.text
                except:
                    print(f"   Response (text): {response.text[:200]}")
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

    def test_recording_proxy_invalid_token(self):
        """Test recording proxy endpoint with invalid token - should return 404"""
        invalid_token = "invalid_token_12345"
        return self.run_test(
            "Recording Proxy - Invalid Token",
            "GET", 
            f"/api/recordings/{invalid_token}/",
            expected_status=404
        )

    def test_batch_recordings_invalid_token(self):
        """Test batch recordings page with invalid token - should return 404"""
        invalid_token = "invalid_batch_token_12345"
        return self.run_test(
            "Batch Recordings Page - Invalid Token",
            "GET",
            f"/api/recordings/batch/{invalid_token}/",
            expected_status=404  # Implementation returns 404 when no recordings found for invalid token
        )

    def test_retell_webhook_call_started(self):
        """Test Retell webhook with call_started event"""
        test_data = {
            "event": "call_started",
            "data": {
                "call_id": f"test_recording_call_{uuid.uuid4().hex[:8]}",
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "direction": "outbound",
                "agent_id": "test_agent_123",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        return self.run_test(
            "Retell Webhook - call_started Event",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=test_data
        )

    def test_retell_webhook_call_ended_with_recording(self):
        """Test Retell webhook with call_ended event including recording URL"""
        call_id = f"test_recording_ended_{uuid.uuid4().hex[:8]}"
        test_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_agent_123",
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "duration_ms": 45000,  # 45 seconds
                "start_timestamp": int((datetime.now().timestamp() - 45) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "agent_hangup",
                "recording_url": "https://example.com/recording.wav",
                "transcript_object": [
                    {
                        "role": "agent",
                        "content": "Hello, how can I help you?"
                    },
                    {
                        "role": "user",
                        "content": "Pressed Button: 1"
                    },
                    {
                        "role": "agent", 
                        "content": "Thank you for pressing 1"
                    }
                ],
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        return self.run_test(
            "Retell Webhook - call_ended with Recording",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=test_data
        )

    def test_retell_webhook_call_analyzed(self):
        """Test Retell webhook with call_analyzed event"""
        test_data = {
            "event": "call_analyzed",
            "data": {
                "call_id": f"test_analyzed_{uuid.uuid4().hex[:8]}",
                "call_analysis": {
                    "user_sentiment": "positive",
                    "call_summary": "Customer inquiry about recording features",
                    "success_rating": "high"
                }
            }
        }
        
        return self.run_test(
            "Retell Webhook - call_analyzed Event",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=test_data
        )

    def test_retell_webhook_transcript_updated(self):
        """Test Retell webhook with transcript_updated event"""
        test_data = {
            "event": "transcript_updated",
            "data": {
                "call_id": f"test_transcript_{uuid.uuid4().hex[:8]}",
                "transcript_object": [
                    {
                        "role": "user",
                        "content": "Pressed Button: 9"
                    }
                ]
            }
        }
        
        return self.run_test(
            "Retell Webhook - transcript_updated Event",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=test_data
        )

    def test_existing_webhook_endpoints(self):
        """Test that existing webhook endpoints still work"""
        
        # Test Telegram webhook
        telegram_data = {
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "from": {
                    "id": self.test_user_id,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": self.test_user_id,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": "/start"
            }
        }
        
        success1, _ = self.run_test(
            "Existing Telegram Webhook",
            "POST", 
            "/api/telegram/webhook/",
            expected_status=200,
            data=telegram_data
        )

        # Test DTMF supervisor check
        dtmf_data = {
            "call_id": f"test_dtmf_{uuid.uuid4().hex[:8]}",
            "args": {
                "digits": "1234",
                "node_name": "PIN Entry Test"
            }
        }
        
        success2, _ = self.run_test(
            "Existing DTMF Supervisor Check",
            "POST",
            "/api/dtmf/supervisor-check",
            expected_status=200,
            data=dtmf_data
        )

        # Test SMS webhook
        sms_data = {
            "to_number": "+1234567890",
            "from_number": "+1987654321",
            "message": "Test SMS for recording features"
        }
        
        success3, _ = self.run_test(
            "Existing SMS Webhook",
            "POST",
            "/api/webhook/sms",
            expected_status=200,
            data=sms_data
        )

        # Test time check
        time_data = {
            "call_id": f"test_time_{uuid.uuid4().hex[:8]}",
            "args": {
                "phone_number": "+1234567890"
            }
        }
        
        success4, _ = self.run_test(
            "Existing Time Check",
            "POST",
            "/api/time-check",
            expected_status=200,
            data=time_data
        )

        return all([success1, success2, success3, success4])

    def test_database_models_via_webhook(self):
        """Test that webhook creates proper database records with recording fields"""
        
        # Create a call with recording requested
        call_id = f"test_db_recording_{uuid.uuid4().hex[:8]}"
        
        # First send call_started
        call_started_data = {
            "event": "call_started",
            "data": {
                "call_id": call_id,
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "direction": "outbound",
                "agent_id": "test_agent_db",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "Database Model Test - call_started",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_started_data
        )

        # Then send call_ended with recording
        call_ended_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_agent_db",
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "duration_ms": 30000,
                "start_timestamp": int((datetime.now().timestamp() - 30) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "user_hangup",
                "recording_url": "https://example.com/test_recording.wav",
                "transcript_object": [
                    {
                        "role": "user",
                        "content": "Pressed Button: 2"
                    }
                ]
            }
        }
        
        success2, _ = self.run_test(
            "Database Model Test - call_ended with recording",
            "POST",
            "/api/webhook/retell", 
            expected_status=200,
            data=call_ended_data
        )

        return success1 and success2

    def test_recording_token_generation(self):
        """Test that recording tokens are generated properly by attempting access"""
        
        # Try to test with a fake but well-formed token
        # Real tokens would be generated by the system and stored in CallRecording model
        fake_token = "abcd1234_test_call_12345_5590563715"
        
        # This should return 404 since the token doesn't exist in the database
        return self.run_test(
            "Recording Token Format Test",
            "GET",
            f"/api/recordings/{fake_token}/",
            expected_status=404  # Expected since this token won't exist in DB
        )

    def check_recording_features_in_env(self):
        """Check that recording-related configurations are in place"""
        print("\n🔍 Checking Recording Features Configuration...")
        
        required_vars = [
            'RETELL_API_KEY',  # Needed for downloading recordings
            'webhook_url',     # Needed for recording URL generation
        ]
        
        try:
            with open('/app/.env', 'r') as f:
                content = f.read()
                
            all_present = True
            for var in required_vars:
                if f"{var}=" in content:
                    print(f"✅ {var}: Present")
                else:
                    print(f"❌ {var}: Missing")
                    all_present = False
                    
            # Check for media directory
            media_dir = "/app/media/recordings"
            if os.path.exists(media_dir):
                print(f"✅ Media recordings directory exists: {media_dir}")
            else:
                print(f"❌ Media recordings directory missing: {media_dir}")
                all_present = False
                
            return all_present
            
        except Exception as e:
            print(f"❌ Could not check recording configuration: {e}")
            return False

    def print_summary(self):
        """Print test results summary"""
        print(f"\n" + "="*60)
        print(f"📊 RECORDING FEATURES TEST SUMMARY")
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
    print("🎙️ Starting Call Outcome Tracking & Recording Features Testing...")
    print(f"Target URL: https://quickstart-43.preview.emergentagent.com")
    print(f"Test User ID: 5590563715")
    print("="*60)
    
    tester = RecordingFeaturesTester()
    
    # Configuration checks
    config_ok = tester.check_recording_features_in_env()
    
    # API endpoint tests
    print(f"\n" + "="*60)
    print("🧪 RUNNING RECORDING FEATURES TESTS")
    print("="*60)
    
    # Test recording proxy endpoints
    tester.test_recording_proxy_invalid_token()
    tester.test_batch_recordings_invalid_token()
    
    # Test Retell webhook events
    tester.test_retell_webhook_call_started()
    tester.test_retell_webhook_call_ended_with_recording()
    tester.test_retell_webhook_call_analyzed()
    tester.test_retell_webhook_transcript_updated()
    
    # Test existing endpoints still work
    tester.test_existing_webhook_endpoints()
    
    # Test database integration
    tester.test_database_models_via_webhook()
    
    # Test recording token format
    tester.test_recording_token_generation()
    
    # Print results
    success = tester.print_summary()
    
    # Overall health check
    print(f"\n" + "="*60)
    print("🏥 RECORDING FEATURES HEALTH")
    print("="*60)
    
    config_score = 1 if config_ok else 0
    api_score = tester.tests_passed
    
    print(f"Configuration Health: {config_score}/1")
    print(f"API Health: {api_score}/{tester.tests_run}")
    
    overall_health = "HEALTHY" if (config_ok and api_score >= tester.tests_run * 0.8) else "NEEDS_ATTENTION"
    print(f"Recording Features Status: {overall_health}")
    
    return 0 if success and config_ok else 1

if __name__ == "__main__":
    sys.exit(main())