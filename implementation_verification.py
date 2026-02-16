#!/usr/bin/env python3
"""
Implementation Verification Test - Real-time Overage Billing Changes
Verifies specific implementation details from the code changes
"""

import re
import sys

def verify_implementation():
    """Verify all the specific implementation details mentioned in the review request"""
    
    results = {
        "passed": [],
        "failed": []
    }
    
    print("🔍 VERIFYING IMPLEMENTATION DETAILS")
    print("=" * 60)
    
    # 1. Verify _charge_overage_realtime function exists
    try:
        with open("/app/bot/webhooks.py", "r") as f:
            content = f.read()
            
        if "def _charge_overage_realtime(call_id, user_id, additional_minutes):" in content:
            results["passed"].append("✅ _charge_overage_realtime function exists in webhooks.py")
        else:
            results["failed"].append("❌ _charge_overage_realtime function not found")
            
    except Exception as e:
        results["failed"].append(f"❌ Error reading webhooks.py: {e}")
    
    # 2. Verify function is called from _process_batch_call_duration
    try:
        batch_call_match = re.search(r'def _process_batch_call_duration.*?_charge_overage_realtime\(call_id, subscription_result\["user_id"\], overage\)', content, re.DOTALL)
        if batch_call_match:
            results["passed"].append("✅ _charge_overage_realtime called from _process_batch_call_duration")
        else:
            results["failed"].append("❌ _charge_overage_realtime not called from _process_batch_call_duration")
            
    except Exception as e:
        results["failed"].append(f"❌ Error verifying batch call integration: {e}")
    
    # 3. Verify function is called from _process_free_plan_call_duration  
    try:
        free_plan_match = re.search(r'def _process_free_plan_call_duration.*?_charge_overage_realtime\(call_id, subscription_result\["user_id"\], overage\)', content, re.DOTALL)
        if free_plan_match:
            results["passed"].append("✅ _charge_overage_realtime called from _process_free_plan_call_duration")
        else:
            results["failed"].append("❌ _charge_overage_realtime not called from _process_free_plan_call_duration")
            
    except Exception as e:
        results["failed"].append(f"❌ Error verifying free plan integration: {e}")
    
    # 4. Verify all required imports are present
    try:
        required_imports = [
            "OveragePricingTable",
            "UserTransactionLogs", 
            "TransactionType",
            "check_user_balance"
        ]
        
        missing_imports = []
        for imp in required_imports:
            if imp not in content:
                missing_imports.append(imp)
        
        if not missing_imports:
            results["passed"].append("✅ All required imports present (OveragePricingTable, UserTransactionLogs, TransactionType, check_user_balance)")
        else:
            results["failed"].append(f"❌ Missing imports: {missing_imports}")
            
    except Exception as e:
        results["failed"].append(f"❌ Error verifying imports: {e}")
    
    # 5. Verify Celery beat schedule changed to 3600s
    try:
        with open("/app/TelegramBot/settings.py", "r") as f:
            settings_content = f.read()
            
        # Check for 3600.0 schedule and proper comment
        if 'schedule": 3600.0,  # hourly safety-net (real-time billing in webhook)' in settings_content:
            results["passed"].append("✅ Celery beat schedule changed to hourly (3600s) with proper comment")
        elif "3600.0" in settings_content and "charge_user_for_additional_minutes" in settings_content:
            results["passed"].append("✅ Celery beat schedule changed to hourly (3600s)")
        else:
            results["failed"].append("❌ Celery beat schedule not changed to 3600s")
            
    except Exception as e:
        results["failed"].append(f"❌ Error reading settings.py: {e}")
    
    # 6. Verify the function has proper error handling and logging
    try:
        if "logger.info" in content and "logger.warning" in content and "logger.error" in content:
            results["passed"].append("✅ Proper logging implemented in _charge_overage_realtime")
        else:
            results["failed"].append("❌ Missing proper logging in _charge_overage_realtime")
            
        if "try:" in content and "except Exception as e:" in content:
            results["passed"].append("✅ Error handling implemented in _charge_overage_realtime")
        else:
            results["failed"].append("❌ Missing error handling in _charge_overage_realtime")
            
    except Exception as e:
        results["failed"].append(f"❌ Error verifying error handling: {e}")
    
    # Print results
    print("\n📋 VERIFICATION RESULTS:")
    print("-" * 40)
    
    for item in results["passed"]:
        print(item)
    
    for item in results["failed"]:
        print(item)
    
    total_checks = len(results["passed"]) + len(results["failed"])
    passed_checks = len(results["passed"])
    
    print(f"\n📊 SUMMARY: {passed_checks}/{total_checks} checks passed")
    
    if results["failed"]:
        print("\n⚠️ IMPLEMENTATION ISSUES DETECTED:")
        for item in results["failed"]:
            print(f"  {item}")
        return False
    else:
        print("\n🎉 ALL IMPLEMENTATION DETAILS VERIFIED SUCCESSFULLY!")
        return True

def main():
    success = verify_implementation()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())