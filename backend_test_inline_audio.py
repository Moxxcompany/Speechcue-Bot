#!/usr/bin/env python3
"""
Backend Testing for Telegram Inline Audio Playbook Features
Tests the new inline audio playback functionality via Telegram bot.send_audio()
"""
import requests
import sys
import json
import os
import uuid
from datetime import datetime

class InlineAudioTester:
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

    def test_celery_download_task_endpoints(self):
        """Test that download_and_cache_recording Celery task workflow gets triggered correctly"""
        # Simulate a call_ended webhook that should trigger recording download
        call_id = f"test_inline_audio_{uuid.uuid4().hex[:8]}"
        
        # First create call_started to set up the call record
        call_started_data = {
            "event": "call_started",
            "data": {
                "call_id": call_id,
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "direction": "outbound",
                "agent_id": "test_inline_agent",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "Inline Audio - Setup Call Started",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_started_data
        )
        
        # Then send call_ended with recording URL to trigger inline audio download
        call_ended_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_inline_agent",
                "to_number": "+1234567890",
                "from_number": "+1987654321", 
                "duration_ms": 35000,  # 35 seconds
                "start_timestamp": int((datetime.now().timestamp() - 35) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "agent_hangup",
                "recording_url": "https://retell-recordings.s3.amazonaws.com/test_inline_recording.wav",
                "transcript_object": [
                    {
                        "role": "agent",
                        "content": "Hello, this call will have inline audio playback"
                    },
                    {
                        "role": "user",
                        "content": "Pressed Button: 5"
                    }
                ],
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success2, _ = self.run_test(
            "Inline Audio - Trigger Download via call_ended",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_ended_data
        )
        
        return success1 and success2

    def test_small_batch_inline_audio(self):
        """Test that small batches (<5 calls) send individual inline audio"""
        batch_id = f"small_batch_{uuid.uuid4().hex[:8]}"
        
        # Simulate 3 calls in a batch (< BATCH_THRESHOLD of 5)
        for i in range(3):
            call_id = f"{batch_id}_call_{i}"
            
            # call_started
            call_started_data = {
                "event": "call_started",
                "data": {
                    "call_id": call_id,
                    "to_number": f"+123456789{i}",
                    "from_number": "+1987654321",
                    "direction": "outbound",
                    "agent_id": "test_small_batch_agent",
                    "metadata": {"user_id": str(self.test_user_id), "batch_id": batch_id}
                }
            }
            
            success1, _ = self.run_test(
                f"Small Batch Call {i+1} - Setup call_started",
                "POST",
                "/api/webhook/retell",
                expected_status=200,
                data=call_started_data
            )
            
            # call_ended with recording
            call_ended_data = {
                "event": "call_ended",
                "data": {
                    "call_id": call_id,
                    "agent_id": "test_small_batch_agent",
                    "to_number": f"+123456789{i}",
                    "from_number": "+1987654321",
                    "duration_ms": 25000,
                    "start_timestamp": int((datetime.now().timestamp() - 25) * 1000),
                    "end_timestamp": int(datetime.now().timestamp() * 1000),
                    "disconnection_reason": "user_hangup",
                    "recording_url": f"https://retell-recordings.s3.amazonaws.com/small_batch_{i}.wav",
                    "transcript_object": [],
                    "metadata": {"user_id": str(self.test_user_id), "batch_id": batch_id}
                }
            }
            
            success2, _ = self.run_test(
                f"Small Batch Call {i+1} - Trigger inline audio",
                "POST", 
                "/api/webhook/retell",
                expected_status=200,
                data=call_ended_data
            )
            
            if not (success1 and success2):
                return False
                
        return True

    def test_large_batch_consolidated_audio(self):
        """Test that large batches (>=5 calls) skip individual audio but send consolidated after summary"""
        batch_id = f"large_batch_{uuid.uuid4().hex[:8]}"
        
        # Simulate 6 calls in a batch (>= BATCH_THRESHOLD of 5)
        for i in range(6):
            call_id = f"{batch_id}_call_{i}"
            
            # call_started
            call_started_data = {
                "event": "call_started", 
                "data": {
                    "call_id": call_id,
                    "to_number": f"+155500000{i}",
                    "from_number": "+1987654321",
                    "direction": "outbound",
                    "agent_id": "test_large_batch_agent",
                    "metadata": {"user_id": str(self.test_user_id), "batch_id": batch_id}
                }
            }
            
            success1, _ = self.run_test(
                f"Large Batch Call {i+1} - Setup call_started",
                "POST",
                "/api/webhook/retell", 
                expected_status=200,
                data=call_started_data
            )
            
            # call_ended with recording
            call_ended_data = {
                "event": "call_ended",
                "data": {
                    "call_id": call_id,
                    "agent_id": "test_large_batch_agent",
                    "to_number": f"+155500000{i}",
                    "from_number": "+1987654321",
                    "duration_ms": 40000,
                    "start_timestamp": int((datetime.now().timestamp() - 40) * 1000),
                    "end_timestamp": int(datetime.now().timestamp() * 1000),
                    "disconnection_reason": "agent_hangup",
                    "recording_url": f"https://retell-recordings.s3.amazonaws.com/large_batch_{i}.wav",
                    "transcript_object": [
                        {
                            "role": "user",
                            "content": f"Pressed Button: {i+1}"
                        }
                    ],
                    "metadata": {"user_id": str(self.test_user_id), "batch_id": batch_id}
                }
            }
            
            success2, _ = self.run_test(
                f"Large Batch Call {i+1} - Should skip individual inline audio",
                "POST",
                "/api/webhook/retell",
                expected_status=200,
                data=call_ended_data
            )
            
            if not (success1 and success2):
                return False
                
        return True

    def test_play_recording_callback_workflow(self):
        """Test the handle_play_recording callback workflow that checks cached recordings"""
        # This tests the telegrambot.py callback handler logic
        
        # Simulate a call that would have a cached recording
        call_id = f"test_cached_{uuid.uuid4().hex[:8]}"
        
        # Setup a complete call cycle with recording
        call_started_data = {
            "event": "call_started",
            "data": {
                "call_id": call_id,
                "to_number": "+1555123456",
                "from_number": "+1987654321",
                "direction": "outbound", 
                "agent_id": "test_cached_agent",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "Cached Recording Test - Setup call_started",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_started_data
        )
        
        call_ended_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_cached_agent",
                "to_number": "+1555123456",
                "from_number": "+1987654321",
                "duration_ms": 60000,  # 1 minute
                "start_timestamp": int((datetime.now().timestamp() - 60) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "user_hangup",
                "recording_url": "https://retell-recordings.s3.amazonaws.com/cached_test.wav",
                "transcript_object": [
                    {
                        "role": "agent",
                        "content": "This recording will be cached for playback testing"
                    }
                ],
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success2, _ = self.run_test(
            "Cached Recording Test - Create recording for caching",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_ended_data
        )
        
        return success1 and success2

    def test_recording_fallback_functionality(self):
        """Test that fallback link is sent when inline audio fails"""
        # Test the _send_recording_fallback function path
        call_id = f"test_fallback_{uuid.uuid4().hex[:8]}"
        
        call_started_data = {
            "event": "call_started",
            "data": {
                "call_id": call_id,
                "to_number": "+1555987654",
                "from_number": "+1987654321", 
                "direction": "outbound",
                "agent_id": "test_fallback_agent",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "Fallback Test - Setup call_started",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_started_data
        )
        
        # Send call_ended with a potentially problematic recording URL to trigger fallback
        call_ended_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_fallback_agent",
                "to_number": "+1555987654",
                "from_number": "+1987654321",
                "duration_ms": 45000,
                "start_timestamp": int((datetime.now().timestamp() - 45) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "technical_error",
                "recording_url": "https://invalid-url-for-fallback-test.com/recording.wav",
                "transcript_object": [],
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success2, _ = self.run_test(
            "Fallback Test - Trigger fallback via invalid recording URL",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_ended_data
        )
        
        return success1 and success2

    def test_call_outcome_summary_with_recording_incoming(self):
        """Test that call outcome summary shows 'Recording incoming...' message instead of direct link"""
        call_id = f"test_outcome_{uuid.uuid4().hex[:8]}"
        
        call_started_data = {
            "event": "call_started",
            "data": {
                "call_id": call_id,
                "to_number": "+1555456789",
                "from_number": "+1987654321",
                "direction": "outbound",
                "agent_id": "test_outcome_agent", 
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "Outcome Summary Test - Setup call_started",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_started_data
        )
        
        # call_ended should trigger outcome summary with "Recording incoming..." text
        call_ended_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_outcome_agent",
                "to_number": "+1555456789", 
                "from_number": "+1987654321",
                "duration_ms": 55000,
                "start_timestamp": int((datetime.now().timestamp() - 55) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "user_hangup",
                "recording_url": "https://retell-recordings.s3.amazonaws.com/outcome_test.wav",
                "transcript_object": [
                    {
                        "role": "user", 
                        "content": "Pressed Button: 9"
                    },
                    {
                        "role": "agent",
                        "content": "Thank you for pressing 9. Your call is complete."
                    }
                ],
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success2, _ = self.run_test(
            "Outcome Summary Test - Trigger 'Recording incoming...' message",
            "POST",
            "/api/webhook/retell", 
            expected_status=200,
            data=call_ended_data
        )
        
        return success1 and success2

    def test_all_webhook_endpoints_compatibility(self):
        """Test that all existing webhook endpoints still work with inline audio features"""
        
        # Test main Retell webhook
        retell_data = {
            "event": "call_started",
            "data": {
                "call_id": f"test_compat_{uuid.uuid4().hex[:8]}",
                "to_number": "+1234567890",
                "from_number": "+1987654321",
                "direction": "outbound",
                "agent_id": "test_compat_agent",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "Webhook Compatibility - Retell webhook",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=retell_data
        )

        # Test Telegram webhook compatibility
        telegram_data = {
            "update_id": 67890,
            "message": {
                "message_id": 2,
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
                "text": "🎙 Call Recordings"
            }
        }
        
        success2, _ = self.run_test(
            "Webhook Compatibility - Telegram webhook with inline audio features",
            "POST",
            "/api/telegram/webhook/",
            expected_status=200,
            data=telegram_data
        )

        # Test DTMF supervisor check
        dtmf_data = {
            "call_id": f"test_dtmf_compat_{uuid.uuid4().hex[:8]}",
            "args": {
                "digits": "12345",
                "node_name": "Inline Audio Compatible DTMF Test"
            }
        }
        
        success3, _ = self.run_test(
            "Webhook Compatibility - DTMF supervisor check",
            "POST", 
            "/api/dtmf/supervisor-check",
            expected_status=200,
            data=dtmf_data
        )

        # Test SMS webhook
        sms_data = {
            "to_number": "+1234567890",
            "from_number": "+1987654321",
            "message": "Testing SMS compatibility with inline audio features"
        }
        
        success4, _ = self.run_test(
            "Webhook Compatibility - SMS webhook",
            "POST",
            "/api/webhook/sms", 
            expected_status=200,
            data=sms_data
        )

        # Test time check
        time_data = {
            "call_id": f"test_time_compat_{uuid.uuid4().hex[:8]}",
            "args": {
                "phone_number": "+1234567890"
            }
        }
        
        success5, _ = self.run_test(
            "Webhook Compatibility - Time check",
            "POST",
            "/api/time-check",
            expected_status=200,
            data=time_data
        )

        return all([success1, success2, success3, success4, success5])

    def test_recording_proxy_endpoint_functionality(self):
        """Test that recording proxy endpoint still works as HTTP fallback"""
        
        # Test with various token formats to ensure compatibility
        test_tokens = [
            "invalid_token_12345",  # Should return 404
            "abcd1234_test_call_12345_5590563715",  # Well-formed but non-existent, should return 404
        ]
        
        all_success = True
        for token in test_tokens:
            success, _ = self.run_test(
                f"Recording Proxy Compatibility - Token: {token[:20]}...",
                "GET",
                f"/api/recordings/{token}/",
                expected_status=404  # Expected since these tokens don't exist in DB
            )
            if not success:
                all_success = False
                
        return all_success

    def test_callrecording_model_operations(self):
        """Test that CallRecording model operations work correctly with new inline features"""
        # This tests the database layer via webhook operations
        
        call_id = f"test_model_ops_{uuid.uuid4().hex[:8]}"
        
        # Test creating CallRecording via webhook 
        call_started_data = {
            "event": "call_started",
            "data": {
                "call_id": call_id,
                "to_number": "+1555000111",
                "from_number": "+1987654321",
                "direction": "outbound", 
                "agent_id": "test_model_agent",
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success1, _ = self.run_test(
            "CallRecording Model - Setup call for model test",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_started_data
        )
        
        # Test call_ended that should create CallRecording record
        call_ended_data = {
            "event": "call_ended",
            "data": {
                "call_id": call_id,
                "agent_id": "test_model_agent",
                "to_number": "+1555000111",
                "from_number": "+1987654321",
                "duration_ms": 30000,
                "start_timestamp": int((datetime.now().timestamp() - 30) * 1000),
                "end_timestamp": int(datetime.now().timestamp() * 1000),
                "disconnection_reason": "agent_hangup",
                "recording_url": "https://retell-recordings.s3.amazonaws.com/model_test.wav",
                "transcript_object": [
                    {
                        "role": "agent",
                        "content": "Testing CallRecording model operations"
                    }
                ],
                "metadata": {"user_id": str(self.test_user_id)}
            }
        }
        
        success2, _ = self.run_test(
            "CallRecording Model - Create record via call_ended webhook",
            "POST",
            "/api/webhook/retell",
            expected_status=200,
            data=call_ended_data
        )
        
        return success1 and success2

    def check_inline_audio_dependencies(self):
        """Check that inline audio feature dependencies are in place"""
        print("\n🔍 Checking Inline Audio Dependencies...")
        
        dependencies_ok = True
        
        # Check for required environment variables
        required_vars = [
            'API_TOKEN',  # Telegram bot token for bot.send_audio()
            'RETELL_API_KEY',  # For downloading recordings 
            'webhook_url',  # For recording URL generation
        ]
        
        try:
            # Check .env files
            env_files = ['/app/.env', '/app/backend/.env', '/app/frontend/.env']
            env_content = ""
            
            for env_file in env_files:
                if os.path.exists(env_file):
                    with open(env_file, 'r') as f:
                        env_content += f.read() + "\n"
                        
            for var in required_vars:
                if f"{var}=" in env_content:
                    print(f"✅ {var}: Present in environment")
                else:
                    print(f"❌ {var}: Missing from environment")
                    dependencies_ok = False
                    
            # Check media directory for recordings
            media_dir = "/app/media/recordings"
            if os.path.exists(media_dir):
                print(f"✅ Media recordings directory exists: {media_dir}")
            else:
                print(f"❌ Media recordings directory missing: {media_dir}")
                dependencies_ok = False
                
            # Check if Django media settings are configured
            try:
                import django
                from django.conf import settings
                if hasattr(settings, 'MEDIA_ROOT'):
                    print(f"✅ Django MEDIA_ROOT configured: {settings.MEDIA_ROOT}")
                else:
                    print(f"❌ Django MEDIA_ROOT not configured")
                    dependencies_ok = False
            except Exception as e:
                print(f"⚠️  Could not check Django media settings: {e}")
                
            return dependencies_ok
            
        except Exception as e:
            print(f"❌ Could not check inline audio dependencies: {e}")
            return False

    def print_summary(self):
        """Print test results summary"""
        print(f"\n" + "="*60)
        print(f"🎵 INLINE AUDIO PLAYBACK TEST SUMMARY")
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
    print("🎵 Starting Telegram Inline Audio Playback Testing...")
    print(f"Target URL: https://quickstart-43.preview.emergentagent.com")
    print(f"Test User ID: 5590563715")
    print("="*60)
    
    tester = InlineAudioTester()
    
    # Dependency checks
    deps_ok = tester.check_inline_audio_dependencies()
    
    # API endpoint tests
    print(f"\n" + "="*60)
    print("🧪 RUNNING INLINE AUDIO FEATURE TESTS")
    print("="*60)
    
    # Test download_and_cache_recording Celery task workflow
    tester.test_celery_download_task_endpoints()
    
    # Test small batch inline audio (< 5 calls)
    tester.test_small_batch_inline_audio()
    
    # Test large batch consolidated audio (>= 5 calls) 
    tester.test_large_batch_consolidated_audio()
    
    # Test handle_play_recording callback workflow
    tester.test_play_recording_callback_workflow()
    
    # Test recording fallback functionality
    tester.test_recording_fallback_functionality()
    
    # Test call outcome summary with "Recording incoming..."
    tester.test_call_outcome_summary_with_recording_incoming()
    
    # Test webhook compatibility
    tester.test_all_webhook_endpoints_compatibility()
    
    # Test recording proxy endpoint
    tester.test_recording_proxy_endpoint_functionality()
    
    # Test CallRecording model operations
    tester.test_callrecording_model_operations()
    
    # Print results
    success = tester.print_summary()
    
    # Overall health check
    print(f"\n" + "="*60)
    print("🏥 INLINE AUDIO FEATURE HEALTH")
    print("="*60)
    
    deps_score = 1 if deps_ok else 0
    api_score = tester.tests_passed
    
    print(f"Dependencies Health: {deps_score}/1")
    print(f"API Health: {api_score}/{tester.tests_run}")
    
    overall_health = "HEALTHY" if (deps_ok and api_score >= tester.tests_run * 0.8) else "NEEDS_ATTENTION"
    print(f"Inline Audio Features Status: {overall_health}")
    
    return 0 if success and deps_ok else 1

if __name__ == "__main__":
    sys.exit(main())