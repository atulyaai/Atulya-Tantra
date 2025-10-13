#!/usr/bin/env python3
"""
Atulya Tantra - Test Runner
Convenient script to run all tests
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from testing import run_all_tests, run_integrity_tests, run_protocol_tests, run_deep_analysis


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(
        description='Atulya Tantra Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py --suite integrity  # Run integrity tests only
  python run_tests.py --suite protocols  # Run protocol tests only
  python run_tests.py --suite analysis   # Run deep analysis only
  python run_tests.py --quiet           # Minimal output
        """
    )
    
    parser.add_argument(
        '--suite',
        choices=['all', 'integrity', 'protocols', 'analysis'],
        default='all',
        help='Test suite to run (default: all)'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output'
    )
    
    args = parser.parse_args()
    
    # Print header
    if not args.quiet:
        print("=" * 70)
        print("🧪 ATULYA TANTRA - TEST RUNNER")
        print("=" * 70)
        print()
    
    # Run selected test suite
    success = False
    
    if args.suite == 'all':
        success = run_all_tests(verbose=not args.quiet)
    elif args.suite == 'integrity':
        if not args.quiet:
            print("Running System Integrity Tests...")
            print()
        success = run_integrity_tests()
    elif args.suite == 'protocols':
        if not args.quiet:
            print("Running Protocol Tests...")
            print()
        success = run_protocol_tests()
    elif args.suite == 'analysis':
        if not args.quiet:
            print("Running Deep Analysis...")
            print()
        success = run_deep_analysis()
    
    # Exit with appropriate code
    if success:
        if not args.quiet:
            print()
            print("=" * 70)
            print("✅ ALL TESTS PASSED!")
            print("=" * 70)
        sys.exit(0)
    else:
        if not args.quiet:
            print()
            print("=" * 70)
            print("❌ SOME TESTS FAILED")
            print("=" * 70)
        sys.exit(1)


if __name__ == '__main__':
    main()

