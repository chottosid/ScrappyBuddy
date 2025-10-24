#!/usr/bin/env python3
"""
Test script to verify monitoring process works correctly
"""

import logging
from database import db
from agents.coordinator_agent import CoordinatorAgent
from models import MonitoringTarget, TargetType

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_single_monitoring():
    """Test monitoring a single target"""
    print("🧪 Testing single target monitoring...")
    
    # Connect to database
    db.connect()
    
    # Create a test target
    test_target = MonitoringTarget(
        url="https://httpbin.org/json",  # Simple JSON endpoint that's reliable
        target_type=TargetType.WEBSITE,
        frequency_minutes=1,
        user_id="test-user",
        name="Test JSON Endpoint"
    )
    
    # Create coordinator and test
    coordinator = CoordinatorAgent()
    
    print(f"Testing target: {test_target.url}")
    
    # First run (no previous content)
    print("\n--- First Run (No Previous Content) ---")
    result1 = coordinator.monitor_target(test_target, previous_content="")
    
    print(f"✅ First run completed")
    print(f"   Error: {result1.error}")
    print(f"   Content length: {len(result1.current_content) if result1.current_content else 0}")
    print(f"   Changes detected: {len(result1.changes_detected)}")
    
    # Second run (with previous content - should detect no changes)
    print("\n--- Second Run (Same Content) ---")
    result2 = coordinator.monitor_target(test_target, previous_content=result1.current_content)
    
    print(f"✅ Second run completed")
    print(f"   Error: {result2.error}")
    print(f"   Content length: {len(result2.current_content) if result2.current_content else 0}")
    print(f"   Changes detected: {len(result2.changes_detected)}")
    
    # Third run (with different previous content - should detect changes)
    print("\n--- Third Run (Different Previous Content) ---")
    result3 = coordinator.monitor_target(test_target, previous_content="This is completely different content")
    
    print(f"✅ Third run completed")
    print(f"   Error: {result3.error}")
    print(f"   Content length: {len(result3.current_content) if result3.current_content else 0}")
    print(f"   Changes detected: {len(result3.changes_detected)}")
    
    if result3.changes_detected:
        for change in result3.changes_detected:
            print(f"   Change summary: {change.summary}")

def test_scheduler():
    """Test the scheduler agent"""
    print("\n🧪 Testing scheduler agent...")
    
    # Connect to database
    db.connect()
    
    coordinator = CoordinatorAgent()
    
    # Test getting targets to monitor
    targets = coordinator.scheduler.get_targets_to_monitor()
    
    print(f"✅ Scheduler found {len(targets)} targets ready for monitoring")
    
    for target in targets:
        print(f"   - {target.url} (freq: {target.frequency_minutes}min)")

def test_full_cycle():
    """Test a full monitoring cycle"""
    print("\n🧪 Testing full monitoring cycle...")
    
    # Connect to database
    db.connect()
    
    coordinator = CoordinatorAgent()
    
    # Run a full monitoring cycle
    coordinator.run_monitoring_cycle()
    
    print("✅ Full monitoring cycle completed")

if __name__ == "__main__":
    print("🔍 Content Monitoring System - Test Suite")
    print("=" * 60)
    
    try:
        test_single_monitoring()
        test_scheduler()
        test_full_cycle()
        
        print("\n🎉 All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()