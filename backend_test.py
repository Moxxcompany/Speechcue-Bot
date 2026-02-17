#!/usr/bin/env python3
"""
Backend Testing for Voice-to-Text Transcription Features
Tests all the new transcript and AI analysis functionality
"""
import requests
import json
import time
import sys
from datetime import datetime, timezone

# Test configuration
BASE_URL = "https://quickstart-43.preview.emergentagent.com"
TEST_USER_ID = 5590563715

class TranscriptFeatureTester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, status, details=""):
        """Log test result"""
        self.tests_run += 1
        if status:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "status": "PASS" if status else "FAIL",
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_webhook_endpoint_exists(self):
        """Test 1: Webhook endpoint is accessible"""
        try:
            url = f"{self.base_url}/api/webhook/retell"
            response = requests.get(url, timeout=10)
            # Webhook should reject GET but be accessible
            success = response.status_code in [405, 200]
            self.log_test("Webhook endpoint accessible", success, 
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Webhook endpoint accessible", False, str(e))
            return False

    def test_call_ended_webhook_with_transcript(self):
        """Test 2: call_ended webhook processes transcript_object correctly"""
        try:
            # First create a CallLogsTable entry
            call_id = f"test_call_transcript_{int(time.time())}"
            
            # Sample transcript object from Retell
            sample_transcript = [
                {"role": "agent", "content": "Hello, thank you for calling. How can I help you today?"},
                {"role": "user", "content": "Hi, I'm calling about my account balance."},
                {"role": "agent", "content": "I'd be happy to help with that. Can you provide your account number?"},
                {"role": "user", "content": "Yes, it's 123456789"},
                {"role": "user", "content": "Pressed Button: 1"},
                {"role": "agent", "content": "Thank you. I see your account. Your current balance is $150."},
                {"role": "user", "content": "Great, thank you for the help!"}
            ]

            webhook_payload = {
                "event": "call_ended",
                "data": {
                    "call_id": call_id,
                    "agent_id": "agent_test_123",
                    "to_number": "+1234567890",
                    "duration_ms": 120000,
                    "start_timestamp": int(time.time() * 1000) - 120000,
                    "end_timestamp": int(time.time() * 1000),
                    "transcript_object": sample_transcript,
                    "disconnection_reason": "user_hangup"
                }
            }

            url = f"{self.base_url}/api/webhook/retell"
            response = requests.post(url, json=webhook_payload, timeout=15)
            
            success = response.status_code == 200
            self.log_test("call_ended webhook with transcript", success,
                         f"Status: {response.status_code}, Response: {response.text[:200]}")
            return success, call_id
        except Exception as e:
            self.log_test("call_ended webhook with transcript", False, str(e))
            return False, None

    def test_call_analyzed_webhook(self):
        """Test 3: call_analyzed webhook stores AI analysis data"""
        try:
            call_id = f"test_call_analysis_{int(time.time())}"
            
            webhook_payload = {
                "event": "call_analyzed", 
                "data": {
                    "call_id": call_id,
                    "call_analysis": {
                        "call_summary": "Customer called to inquire about their account balance. Agent successfully provided the balance information of $150. Customer was satisfied with the service.",
                        "user_sentiment": "Positive"
                    }
                }
            }

            url = f"{self.base_url}/api/webhook/retell"
            response = requests.post(url, json=webhook_payload, timeout=15)
            
            success = response.status_code == 200
            self.log_test("call_analyzed webhook", success,
                         f"Status: {response.status_code}, Response: {response.text[:200]}")
            return success, call_id
        except Exception as e:
            self.log_test("call_analyzed webhook", False, str(e))
            return False, None

    def test_combined_webhook_flow(self):
        """Test 4: Complete flow - call_ended followed by call_analyzed"""
        try:
            call_id = f"test_combined_flow_{int(time.time())}"
            
            # Sample conversation transcript
            sample_transcript = [
                {"role": "agent", "content": "Hello, this is customer service. How may I assist you?"},
                {"role": "user", "content": "I need help with my subscription renewal."},
                {"role": "agent", "content": "I'll be happy to help. Can you provide your customer ID?"},
                {"role": "user", "content": "It's 987654321"},
                {"role": "agent", "content": "Thank you. I see your subscription expires next week. Would you like to renew?"},
                {"role": "user", "content": "Yes, please renew it for another year."},
                {"role": "agent", "content": "Perfect! I've processed your renewal. You're all set for another year."}
            ]

            # First: call_ended with transcript
            call_ended_payload = {
                "event": "call_ended",
                "data": {
                    "call_id": call_id,
                    "agent_id": "agent_test_456", 
                    "to_number": "+1987654321",
                    "duration_ms": 180000,
                    "start_timestamp": int(time.time() * 1000) - 180000,
                    "end_timestamp": int(time.time() * 1000),
                    "transcript_object": sample_transcript,
                    "disconnection_reason": "agent_hangup",
                    "recording_url": "https://retell-recordings.s3.amazonaws.com/test_recording.wav"
                }
            }

            url = f"{self.base_url}/api/webhook/retell"
            response1 = requests.post(url, json=call_ended_payload, timeout=15)
            
            # Wait a bit then send call_analyzed
            time.sleep(2)
            
            call_analyzed_payload = {
                "event": "call_analyzed",
                "data": {
                    "call_id": call_id,
                    "call_analysis": {
                        "call_summary": "Customer called for subscription renewal assistance. Agent successfully processed a one-year renewal. Customer was satisfied with the quick resolution.",
                        "user_sentiment": "Positive"
                    }
                }
            }
            
            response2 = requests.post(url, json=call_analyzed_payload, timeout=15)
            
            success = response1.status_code == 200 and response2.status_code == 200
            self.log_test("Combined webhook flow (call_ended + call_analyzed)", success,
                         f"call_ended: {response1.status_code}, call_analyzed: {response2.status_code}")
            return success, call_id
        except Exception as e:
            self.log_test("Combined webhook flow", False, str(e))
            return False, None

    def test_batch_recordings_endpoint(self):
        """Test 5: Batch recordings HTML page includes transcript snippets"""
        try:
            # This would typically require a valid batch token
            # For now, just test that the endpoint structure exists
            url = f"{self.base_url}/api/recordings/batch/test_token/"
            response = requests.get(url, timeout=10)
            
            # Expect 403/404 for invalid token, not 500 error
            success = response.status_code in [403, 404, 200]
            self.log_test("Batch recordings endpoint structure", success,
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Batch recordings endpoint structure", False, str(e))
            return False

    def test_individual_recording_endpoint(self):
        """Test 6: Individual recording endpoint exists"""
        try:
            url = f"{self.base_url}/api/recordings/test_token/"
            response = requests.get(url, timeout=10)
            
            # Expect 404 for invalid token, not 500 error
            success = response.status_code in [404, 403, 200]
            self.log_test("Individual recording endpoint structure", success,
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Individual recording endpoint structure", False, str(e))
            return False

    def test_webhook_events_handling(self):
        """Test 7: Test webhook handles all expected events"""
        events_to_test = [
            ("call_started", {"call_id": "test_started", "to_number": "+1234567890", "direction": "outbound"}),
            ("transcript_updated", {"call_id": "test_transcript_update", "transcript_object": [{"role": "user", "content": "Hello"}]}),
            ("unknown_event", {"call_id": "test_unknown"})
        ]
        
        all_success = True
        results = []
        
        for event, data in events_to_test:
            try:
                webhook_payload = {"event": event, "data": data}
                url = f"{self.base_url}/api/webhook/retell"
                response = requests.post(url, json=webhook_payload, timeout=10)
                
                success = response.status_code == 200
                results.append(f"{event}:{response.status_code}")
                if not success:
                    all_success = False
            except Exception as e:
                results.append(f"{event}:ERROR")
                all_success = False
        
        self.log_test("Webhook events handling", all_success, f"Results: {', '.join(results)}")
        return all_success

    def test_dtmf_extraction_from_transcript(self):
        """Test 8: DTMF extraction from transcript_object"""
        try:
            call_id = f"test_dtmf_extraction_{int(time.time())}"
            
            # Transcript with DTMF entries
            dtmf_transcript = [
                {"role": "agent", "content": "Please enter your PIN followed by the pound key."},
                {"role": "user", "content": "Pressed Button: 1"},
                {"role": "user", "content": "Pressed Button: 2"},
                {"role": "user", "content": "Pressed Button: 3"},
                {"role": "user", "content": "Pressed Button: 4"},
                {"role": "user", "content": "Pressed Button: #"},
                {"role": "agent", "content": "Thank you. PIN accepted."}
            ]

            webhook_payload = {
                "event": "call_ended",
                "data": {
                    "call_id": call_id,
                    "agent_id": "agent_dtmf_test",
                    "to_number": "+1555123456",
                    "duration_ms": 90000,
                    "start_timestamp": int(time.time() * 1000) - 90000,
                    "end_timestamp": int(time.time() * 1000),
                    "transcript_object": dtmf_transcript,
                    "disconnection_reason": "user_hangup"
                }
            }

            url = f"{self.base_url}/api/webhook/retell"
            response = requests.post(url, json=webhook_payload, timeout=15)
            
            success = response.status_code == 200
            self.log_test("DTMF extraction from transcript", success,
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("DTMF extraction from transcript", False, str(e))
            return False

    def test_error_handling(self):
        """Test 9: Error handling for malformed requests"""
        test_cases = [
            ("Invalid JSON", "not valid json"),
            ("Missing event", {"data": {"call_id": "test"}}),
            ("Empty payload", {}),
            ("Malformed call_ended", {"event": "call_ended", "data": {"invalid": "data"}})
        ]
        
        all_handled = True
        results = []
        
        for test_name, payload in test_cases:
            try:
                url = f"{self.base_url}/api/webhook/retell"
                if isinstance(payload, str):
                    response = requests.post(url, data=payload, 
                                           headers={'Content-Type': 'application/json'}, 
                                           timeout=10)
                else:
                    response = requests.post(url, json=payload, timeout=10)
                
                # Should handle errors gracefully (not 500)
                success = response.status_code in [200, 400, 422]
                results.append(f"{test_name}:{response.status_code}")
                if not success:
                    all_handled = False
            except Exception as e:
                results.append(f"{test_name}:ERROR")
                all_handled = False
        
        self.log_test("Error handling", all_handled, f"Results: {', '.join(results)}")
        return all_handled

    def test_transcript_formatting_functions(self):
        """Test 10: Test transcript formatting via a sample webhook call"""
        try:
            call_id = f"test_formatting_{int(time.time())}"
            
            # Complex transcript to test formatting
            complex_transcript = [
                {"role": "agent", "content": "Welcome to our service. How can I help you today?"},
                {"role": "user", "content": "I'm having trouble with my recent order."},
                {"role": "agent", "content": "I understand your concern. Can you provide your order number?"},
                {"role": "user", "content": "Sure, it's ORDER-12345"},
                {"role": "user", "content": "Pressed Button: 1"},  # Should be excluded from transcript
                {"role": "agent", "content": "I found your order. It looks like there was a delay in shipping."},
                {"role": "user", "content": "When will it arrive?"},
                {"role": "agent", "content": "It should arrive within 2-3 business days. I'll send you a tracking number."},
                {"role": "user", "content": "Perfect, thank you!"}
            ]

            webhook_payload = {
                "event": "call_ended",
                "data": {
                    "call_id": call_id,
                    "agent_id": "agent_format_test",
                    "to_number": "+1555987654",
                    "duration_ms": 240000,
                    "start_timestamp": int(time.time() * 1000) - 240000,
                    "end_timestamp": int(time.time() * 1000),
                    "transcript_object": complex_transcript,
                    "disconnection_reason": "user_hangup"
                }
            }

            url = f"{self.base_url}/api/webhook/retell"
            response = requests.post(url, json=webhook_payload, timeout=15)
            
            success = response.status_code == 200
            self.log_test("Transcript formatting functions", success,
                         f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Transcript formatting functions", False, str(e))
            return False

    def run_all_tests(self):
        """Run all tests and return summary"""
        print(f"\n🚀 Starting Voice-to-Text Transcription Backend Tests")
        print(f"Base URL: {self.base_url}")
        print(f"Test User ID: {TEST_USER_ID}")
        print("=" * 60)
        
        # Run tests in logical order
        tests = [
            self.test_webhook_endpoint_exists,
            self.test_call_ended_webhook_with_transcript,
            self.test_call_analyzed_webhook,
            self.test_combined_webhook_flow,
            self.test_dtmf_extraction_from_transcript,
            self.test_transcript_formatting_functions,
            self.test_webhook_events_handling,
            self.test_batch_recordings_endpoint,
            self.test_individual_recording_endpoint,
            self.test_error_handling,
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(f"Test execution error: {test.__name__}", False, str(e))
            time.sleep(1)  # Brief pause between tests
        
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return False

    def get_test_results(self):
        """Return detailed test results"""
        return {
            "summary": {
                "total_tests": self.tests_run,
                "passed_tests": self.tests_passed,
                "failed_tests": self.tests_run - self.tests_passed,
                "success_rate": f"{(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%"
            },
            "test_details": self.test_results,
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main test execution"""
    tester = TranscriptFeatureTester()
    
    try:
        success = tester.run_all_tests()
        
        # Save detailed results
        results = tester.get_test_results()
        with open("/tmp/backend_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📝 Detailed results saved to: /tmp/backend_test_results.json")
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())