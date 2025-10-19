"""
Atulya Tantra - Testing Module
Consolidated testing infrastructure
"""

from .test_all import run_all_tests

__all__ = ['run_all_tests']


def run_tests(verbose=True):
    """
    Run all tests - unified entry point
    
    Args:
        verbose: Print detailed output
        
    Returns:
        True if all tests pass
    """
    return run_all_tests(verbose=verbose)
