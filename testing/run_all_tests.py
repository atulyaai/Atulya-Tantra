#!/usr/bin/env python3
"""
Atulya Tantra - Unified Test Runner
Single entry point for all tests
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from testing import (
    run_integrity_tests,
    run_protocol_tests,
    run_deep_analysis
)


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(
        description='Atulya Tantra Unified Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--suite',
        choices=['all', 'integrity', 'protocols', 'analysis'],
        default='all',
        help='Test suite to run'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        print("=" * 70)
        print("🧪 ATULYA TANTRA - UNIFIED TEST RUNNER")
        print(f"📋 Suite: {args.suite}")
        print("=" * 70)
        print()
    
    results = {}
    
    if args.suite == 'all':
        results['integrity'] = run_integrity_tests()
        results['protocols'] = run_protocol_tests()
        results['analysis'] = run_deep_analysis()
    elif args.suite == 'integrity':
        results['integrity'] = run_integrity_tests()
    elif args.suite == 'protocols':
        results['protocols'] = run_protocol_tests()
    elif args.suite == 'analysis':
        results['analysis'] = run_deep_analysis()
    
    # Summary
    if args.verbose and len(results) > 1:
        print("\n" + "=" * 70)
        print("📊 OVERALL RESULTS")
        print("=" * 70)
        for suite, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"  {suite.upper()}: {status}")
        print("=" * 70)
    
    # Exit with appropriate code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()

