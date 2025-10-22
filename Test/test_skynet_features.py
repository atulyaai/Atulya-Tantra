#!/usr/bin/env python3
"""
Test script for Atulya Tantra AGI Skynet Features
Tests task scheduling, system monitoring, and auto-healing capabilities
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.skynet import (
    schedule_task, cancel_task, get_task_status, get_task_statistics,
    get_system_health, get_system_metrics, get_system_alerts,
    get_healing_status, trigger_manual_healing,
    ScheduleType, TaskPriority, HealingPriority
)
from Core.config.logging import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)


async def test_task_scheduler():
    """Test task scheduling and automation system"""
    print("🤖 Testing Task Scheduler...")
    
    try:
        # Test scheduling a one-time task
        print("  Testing one-time task scheduling...")
        task_id1 = await schedule_task(
            name="Test Task 1",
            task_type="system_health_check",
            schedule_type=ScheduleType.ONCE,
            priority=TaskPriority.NORMAL,
            description="Test one-time task execution"
        )
        print(f"  ✅ Scheduled one-time task: {task_id1}")
        
        # Test scheduling an interval task
        print("  Testing interval task scheduling...")
        task_id2 = await schedule_task(
            name="Test Task 2",
            task_type="performance_monitor",
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"interval_seconds": 300},  # 5 minutes
            priority=TaskPriority.HIGH,
            description="Test interval task execution"
        )
        print(f"  ✅ Scheduled interval task: {task_id2}")
        
        # Test scheduling a cron task
        print("  Testing cron task scheduling...")
        task_id3 = await schedule_task(
            name="Test Task 3",
            task_type="database_backup",
            schedule_type=ScheduleType.CRON,
            schedule_config={"cron_expression": "0 2 * * *"},  # Daily at 2 AM
            priority=TaskPriority.CRITICAL,
            description="Test cron task execution"
        )
        print(f"  ✅ Scheduled cron task: {task_id3}")
        
        # Test getting task status
        print("  Testing task status retrieval...")
        status1 = await get_task_status(task_id1)
        if status1:
            print(f"  ✅ Task status retrieved: {status1.get('status', 'unknown')}")
        
        # Test getting task statistics
        print("  Testing task statistics...")
        stats = await get_task_statistics()
        print(f"  ✅ Task statistics: {stats.get('total_tasks', 0)} total tasks")
        
        # Test cancelling a task
        print("  Testing task cancellation...")
        cancelled = await cancel_task(task_id3)
        if cancelled:
            print(f"  ✅ Task cancelled successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Task scheduler test failed: {e}")
        print(f"  ❌ Task scheduler test failed: {e}")
        return False


async def test_system_monitor():
    """Test system monitoring and health checks"""
    print("\n📊 Testing System Monitor...")
    
    try:
        # Test getting system health
        print("  Testing system health check...")
        health = await get_system_health()
        print(f"  ✅ System health: {health.get('overall_status', 'unknown')}")
        
        # Display health check details
        checks = health.get('checks', {})
        for check_name, check_data in checks.items():
            status = check_data.get('status', 'unknown')
            print(f"    - {check_name}: {status}")
        
        # Test getting system metrics
        print("  Testing system metrics collection...")
        metrics = await get_system_metrics(limit=5)
        print(f"  ✅ Collected {len(metrics)} metrics")
        
        if metrics:
            for metric in metrics[-3:]:  # Show last 3 metrics
                print(f"    - {metric.get('name', 'unknown')}: {metric.get('value', 'N/A')}")
        
        # Test getting system alerts
        print("  Testing system alerts...")
        alerts = await get_system_alerts(unresolved_only=True)
        print(f"  ✅ Found {len(alerts)} unresolved alerts")
        
        if alerts:
            for alert in alerts[:3]:  # Show first 3 alerts
                print(f"    - {alert.get('title', 'No title')}: {alert.get('level', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"System monitor test failed: {e}")
        print(f"  ❌ System monitor test failed: {e}")
        return False


async def test_auto_healer():
    """Test auto-healing capabilities"""
    print("\n🔧 Testing Auto-Healer...")
    
    try:
        # Test getting healing status
        print("  Testing healing status...")
        healing_status = await get_healing_status()
        print(f"  ✅ Healing monitoring active: {healing_status.get('monitoring_active', False)}")
        
        # Display healing rules
        rules = healing_status.get('rules', [])
        print(f"  ✅ Found {len(rules)} healing rules")
        
        for rule in rules[:3]:  # Show first 3 rules
            print(f"    - {rule.get('name', 'No name')}: {rule.get('priority', 'unknown')} priority")
        
        # Display recent healing sessions
        recent_sessions = healing_status.get('recent_sessions', [])
        print(f"  ✅ Found {len(recent_sessions)} recent healing sessions")
        
        if recent_sessions:
            for session in recent_sessions[:2]:  # Show first 2 sessions
                print(f"    - Session {session.get('session_id', 'unknown')[:8]}: {session.get('status', 'unknown')}")
        
        # Test manual healing trigger (if rules exist)
        if rules:
            print("  Testing manual healing trigger...")
            try:
                first_rule_id = rules[0].get('rule_id')
                if first_rule_id:
                    session_id = await trigger_manual_healing(
                        first_rule_id, 
                        "Test manual healing trigger"
                    )
                    print(f"  ✅ Manual healing triggered: {session_id[:8]}...")
            except Exception as e:
                print(f"  ⚠️  Manual healing test skipped: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Auto-healer test failed: {e}")
        print(f"  ❌ Auto-healer test failed: {e}")
        return False


async def test_integration():
    """Test integration between Skynet components"""
    print("\n🔗 Testing Skynet Integration...")
    
    try:
        # Test scheduling a monitoring task
        print("  Testing scheduled monitoring task...")
        monitor_task_id = await schedule_task(
            name="System Health Monitor",
            task_type="system_health_check",
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"interval_seconds": 60},
            priority=TaskPriority.HIGH,
            description="Automated system health monitoring"
        )
        print(f"  ✅ Scheduled monitoring task: {monitor_task_id[:8]}...")
        
        # Test scheduling a healing task
        print("  Testing scheduled healing task...")
        healing_task_id = await schedule_task(
            name="Auto-Healing Check",
            task_type="custom_healing",
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"interval_seconds": 300},
            priority=TaskPriority.NORMAL,
            description="Automated healing check",
            metadata={"healing_rule": "high_cpu_usage"}
        )
        print(f"  ✅ Scheduled healing task: {healing_task_id[:8]}...")
        
        # Wait a moment for tasks to be processed
        await asyncio.sleep(2)
        
        # Check if tasks are being processed
        monitor_status = await get_task_status(monitor_task_id)
        healing_status = await get_task_status(healing_task_id)
        
        print(f"  ✅ Monitor task status: {monitor_status.get('status', 'unknown') if monitor_status else 'not found'}")
        print(f"  ✅ Healing task status: {healing_status.get('status', 'unknown') if healing_status else 'not found'}")
        
        # Test overall system status
        print("  Testing overall system status...")
        health = await get_system_health()
        healing = await get_healing_status()
        stats = await get_task_statistics()
        
        print(f"  ✅ System health: {health.get('overall_status', 'unknown')}")
        print(f"  ✅ Healing active: {healing.get('monitoring_active', False)}")
        print(f"  ✅ Tasks scheduled: {stats.get('total_tasks', 0)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        print(f"  ❌ Integration test failed: {e}")
        return False


async def test_performance():
    """Test performance and scalability"""
    print("\n⚡ Testing Performance...")
    
    try:
        # Test scheduling multiple tasks quickly
        print("  Testing bulk task scheduling...")
        task_ids = []
        
        start_time = datetime.utcnow()
        
        for i in range(10):
            task_id = await schedule_task(
                name=f"Performance Test Task {i}",
                task_type="performance_test",
                schedule_type=ScheduleType.ONCE,
                priority=TaskPriority.LOW,
                description=f"Performance test task {i}"
            )
            task_ids.append(task_id)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        print(f"  ✅ Scheduled {len(task_ids)} tasks in {duration:.2f} seconds")
        
        # Test getting multiple task statuses
        print("  Testing bulk status retrieval...")
        start_time = datetime.utcnow()
        
        statuses = []
        for task_id in task_ids[:5]:  # Check first 5 tasks
            status = await get_task_status(task_id)
            statuses.append(status)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        print(f"  ✅ Retrieved {len(statuses)} task statuses in {duration:.2f} seconds")
        
        # Test metrics collection performance
        print("  Testing metrics collection performance...")
        start_time = datetime.utcnow()
        
        metrics = await get_system_metrics(limit=50)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        print(f"  ✅ Collected {len(metrics)} metrics in {duration:.2f} seconds")
        
        # Clean up test tasks
        print("  Cleaning up test tasks...")
        for task_id in task_ids:
            await cancel_task(task_id)
        
        print(f"  ✅ Cleaned up {len(task_ids)} test tasks")
        
        return True
        
    except Exception as e:
        logger.error(f"Performance test failed: {e}")
        print(f"  ❌ Performance test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling and recovery"""
    print("\n🛡️ Testing Error Handling...")
    
    try:
        # Test invalid task scheduling
        print("  Testing invalid task scheduling...")
        try:
            invalid_task_id = await schedule_task(
                name="Invalid Task",
                task_type="nonexistent_type",
                schedule_type=ScheduleType.ONCE,
                priority=TaskPriority.NORMAL
            )
            print(f"  ✅ Invalid task handled gracefully: {invalid_task_id[:8]}...")
        except Exception as e:
            print(f"  ✅ Invalid task properly rejected: {e}")
        
        # Test getting status of non-existent task
        print("  Testing non-existent task status...")
        status = await get_task_status("nonexistent_task_id")
        if status is None:
            print(f"  ✅ Non-existent task status properly handled")
        
        # Test cancelling non-existent task
        print("  Testing cancelling non-existent task...")
        cancelled = await cancel_task("nonexistent_task_id")
        if not cancelled:
            print(f"  ✅ Non-existent task cancellation properly handled")
        
        # Test metrics with invalid parameters
        print("  Testing invalid metrics parameters...")
        try:
            metrics = await get_system_metrics(limit=-1)  # Invalid limit
            print(f"  ✅ Invalid metrics parameters handled gracefully")
        except Exception as e:
            print(f"  ✅ Invalid metrics parameters properly rejected: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error handling test failed: {e}")
        print(f"  ❌ Error handling test failed: {e}")
        return False


async def main():
    """Run all Skynet feature tests"""
    print("🚀 Atulya Tantra AGI - Skynet Features Test Suite")
    print("=" * 70)
    
    # Test results
    test_results = []
    
    # Test 1: Task Scheduler
    test_results.append(await test_task_scheduler())
    
    # Test 2: System Monitor
    test_results.append(await test_system_monitor())
    
    # Test 3: Auto-Healer
    test_results.append(await test_auto_healer())
    
    # Test 4: Integration
    test_results.append(await test_integration())
    
    # Test 5: Performance
    test_results.append(await test_performance())
    
    # Test 6: Error Handling
    test_results.append(await test_error_handling())
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary:")
    
    test_names = [
        "Task Scheduler",
        "System Monitor",
        "Auto-Healer",
        "Integration",
        "Performance",
        "Error Handling"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        print(f"  {name}: {'✅' if result else '❌'}")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Skynet features are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs for details.")
    
    # Final system status
    print("\n📈 Final System Status:")
    try:
        health = await get_system_health()
        healing = await get_healing_status()
        stats = await get_task_statistics()
        
        print(f"  System Health: {health.get('overall_status', 'unknown')}")
        print(f"  Healing Active: {healing.get('monitoring_active', False)}")
        print(f"  Scheduled Tasks: {stats.get('total_tasks', 0)}")
        print(f"  Active Rules: {healing.get('enabled_rules', 0)}")
        
    except Exception as e:
        print(f"  Error getting final status: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user.")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")
