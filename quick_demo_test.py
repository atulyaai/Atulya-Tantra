#!/usr/bin/env python3
"""
Quick Demo Test Runner
Tests existing demo files with strict time limits
"""

import os
import sys
import asyncio
import time
import signal
import subprocess
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
TEST_CONFIG = {
    "max_demo_time": 60,  # 1 minute per demo
    "max_total_time": 300,  # 5 minutes total
    "demos_to_test": [
        "working_jarvis_demo.py",
        "final_jarvis_demo.py", 
        "comprehensive_jarvis_test.py"
    ]
}

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    """Handle timeout signals"""
    raise TimeoutError("Demo timed out")

def run_demo_with_timeout(demo_file: str, timeout: int = 60) -> dict:
    """Run a demo file with timeout protection"""
    logger.info(f"🚀 Testing {demo_file}...")
    
    start_time = time.time()
    
    try:
        # Set up timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        # Run the demo
        result = subprocess.run(
            [sys.executable, demo_file],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Cancel timeout
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        
        duration = time.time() - start_time
        
        return {
            'file': demo_file,
            'status': 'SUCCESS' if result.returncode == 0 else 'FAILED',
            'duration': duration,
            'returncode': result.returncode,
            'stdout': result.stdout[-500:],  # Last 500 chars
            'stderr': result.stderr[-500:] if result.stderr else None
        }
        
    except TimeoutError:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        
        duration = time.time() - start_time
        return {
            'file': demo_file,
            'status': 'TIMEOUT',
            'duration': duration,
            'returncode': -1,
            'stdout': '',
            'stderr': f'Demo timed out after {timeout} seconds'
        }
        
    except Exception as e:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        
        duration = time.time() - start_time
        return {
            'file': demo_file,
            'status': 'ERROR',
            'duration': duration,
            'returncode': -1,
            'stdout': '',
            'stderr': str(e)
        }

def test_core_imports():
    """Test Core module imports"""
    logger.info("🔍 Testing Core module imports...")
    
    try:
        # Test basic imports
        sys.path.insert(0, '.')
        
        # Test config imports
        from Core.config import exceptions
        logger.info("✅ Core.config.exceptions imported successfully")
        
        # Test settings
        from Core.config.settings import settings
        logger.info("✅ Core.config.settings imported successfully")
        
        # Test AGI core
        from Core import agi_core
        logger.info("✅ Core.agi_core imported successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Core import failed: {e}")
        return False

def test_demo_files():
    """Test demo files exist and are executable"""
    logger.info("📁 Checking demo files...")
    
    results = []
    for demo in TEST_CONFIG["demos_to_test"]:
        if os.path.exists(demo):
            if os.access(demo, os.R_OK):
                results.append({
                    'file': demo,
                    'status': 'EXISTS',
                    'readable': True
                })
                logger.info(f"✅ {demo} exists and is readable")
            else:
                results.append({
                    'file': demo,
                    'status': 'NO_READ',
                    'readable': False
                })
                logger.error(f"❌ {demo} exists but not readable")
        else:
            results.append({
                'file': demo,
                'status': 'MISSING',
                'readable': False
            })
            logger.error(f"❌ {demo} not found")
    
    return results

def run_quick_test():
    """Run the quick test suite"""
    print("🚀 Quick Demo Test Runner")
    print("=" * 50)
    print(f"⏱️  Time Limits:")
    print(f"   • Per demo: {TEST_CONFIG['max_demo_time']} seconds")
    print(f"   • Total time: {TEST_CONFIG['max_total_time']} seconds")
    print()
    
    start_time = time.time()
    results = []
    
    # Test 1: Core Imports
    print("🔍 Testing Core Imports...")
    core_imports_ok = test_core_imports()
    results.append({
        'test': 'Core Imports',
        'status': 'PASS' if core_imports_ok else 'FAIL',
        'duration': 0
    })
    
    if not core_imports_ok:
        print("❌ Core imports failed - skipping demo tests")
        return results
    
    # Test 2: Demo Files
    print("\n📁 Testing Demo Files...")
    demo_files = test_demo_files()
    for demo_result in demo_files:
        results.append({
            'test': f"Demo File: {demo_result['file']}",
            'status': demo_result['status'],
            'duration': 0
        })
    
    # Test 3: Run Demos (only if files exist and are readable)
    print("\n🚀 Running Demo Tests...")
    for demo in TEST_CONFIG["demos_to_test"]:
        if os.path.exists(demo) and os.access(demo, os.R_OK):
            # Check if we're still within time limit
            elapsed = time.time() - start_time
            if elapsed > TEST_CONFIG["max_total_time"]:
                logger.warning(f"⏰ Total time limit reached, skipping remaining demos")
                break
            
            # Run the demo
            demo_result = run_demo_with_timeout(demo, TEST_CONFIG["max_demo_time"])
            results.append({
                'test': f"Demo: {demo}",
                'status': demo_result['status'],
                'duration': demo_result['duration'],
                'details': {
                    'returncode': demo_result['returncode'],
                    'stdout_preview': demo_result['stdout'][-100:] if demo_result['stdout'] else '',
                    'stderr_preview': demo_result['stderr'][-100:] if demo_result['stderr'] else ''
                }
            })
            
            # Show preview of output
            if demo_result['status'] == 'SUCCESS':
                print(f"✅ {demo} - SUCCESS ({demo_result['duration']:.1f}s)")
                if demo_result['stdout']:
                    print(f"   Output preview: {demo_result['stdout'][-100:]}...")
            elif demo_result['status'] == 'TIMEOUT':
                print(f"⏰ {demo} - TIMEOUT ({demo_result['duration']:.1f}s)")
            else:
                print(f"❌ {demo} - {demo_result['status']} ({demo_result['duration']:.1f}s)")
                if demo_result['stderr']:
                    print(f"   Error: {demo_result['stderr'][-100:]}...")
        else:
            print(f"⏭️  {demo} - SKIPPED (file not found or not readable)")
    
    # Summary
    total_time = time.time() - start_time
    passed = sum(1 for r in results if r['status'] in ['PASS', 'SUCCESS'])
    failed = sum(1 for r in results if r['status'] in ['FAIL', 'FAILED', 'ERROR', 'TIMEOUT'])
    
    print(f"\n📊 Test Summary:")
    print(f"   • Total time: {total_time:.2f} seconds")
    print(f"   • Tests run: {len(results)}")
    print(f"   • Passed: {passed}")
    print(f"   • Failed: {failed}")
    print(f"   • Success rate: {(passed/len(results))*100:.1f}%")
    
    print(f"\n📋 Detailed Results:")
    for result in results:
        status_icon = "✅" if result['status'] in ['PASS', 'SUCCESS'] else "❌"
        print(f"   {status_icon} {result['test']} - {result['status']} ({result['duration']:.1f}s)")
        if 'details' in result and result['details'].get('stderr_preview'):
            print(f"      Error: {result['details']['stderr_preview']}")
    
    return results

if __name__ == "__main__":
    try:
        # Set up signal handlers
        signal.signal(signal.SIGALRM, timeout_handler)
        
        # Run the quick test
        results = run_quick_test()
        
        # Exit with appropriate code
        failed_tests = sum(1 for r in results if r['status'] in ['FAIL', 'FAILED', 'ERROR', 'TIMEOUT'])
        sys.exit(0 if failed_tests == 0 else 1)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        logger.error(f"Test runner failed: {e}")
        sys.exit(1)