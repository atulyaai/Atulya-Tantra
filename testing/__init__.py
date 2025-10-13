"""
Atulya Tantra - Testing Module
Comprehensive testing infrastructure for our system
"""

from .test_system_integrity import run_all_tests as run_integrity_tests
from .test_protocols import run_protocol_tests
from .test_deep_analysis import run_deep_analysis

__all__ = [
    'run_integrity_tests',
    'run_protocol_tests',
    'run_deep_analysis',
]


def run_all_tests(verbose: bool = True):
    """
    Run all test suites
    
    Args:
        verbose: Print detailed output
        
    Returns:
        True if all tests pass
    """
    if verbose:
        print("=" * 70)
        print("🧪 RUNNING ALL TEST SUITES")
        print("=" * 70)
    
    results = {
        'integrity': run_integrity_tests(),
        'protocols': run_protocol_tests(),
        'deep_analysis': run_deep_analysis(),
    }
    
    if verbose:
        print("\n" + "=" * 70)
        print("📊 OVERALL TEST RESULTS")
        print("=" * 70)
        for suite, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"  {suite.upper()}: {status}")
        print("=" * 70)
    
    return all(results.values())
