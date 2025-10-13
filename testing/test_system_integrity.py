"""
JARVIS Protocol - System Integrity Test Suite
Ensures all core components are properly configured
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDirectoryStructure(unittest.TestCase):
    """Verify core directory structure"""
    
    def setUp(self):
        self.root = Path(__file__).parent.parent
        
    def test_core_directories_exist(self):
        """Test that all core directories exist"""
        required_dirs = [
            'models',
            'configuration',
            'automation',
            'testing',
            'webui',
            'others'
        ]
        
        for dir_path in required_dirs:
            full_path = self.root / dir_path
            self.assertTrue(
                full_path.exists(),
                f"Required directory missing: {dir_path}"
            )


class TestCriticalFiles(unittest.TestCase):
    """Verify critical files exist"""
    
    def setUp(self):
        self.root = Path(__file__).parent.parent
        
    def test_core_files_exist(self):
        """Test that all core files exist"""
        required_files = [
            '__version__.py',
            'VERSION',
            'README.md',
            'LICENSE',
            'requirements.txt',
            '.gitignore',
            'configuration/settings.py',
            'automation/agent_orchestrator.py',
            'webui/app.html',
            'testing/test_system_integrity.py',
        ]
        
        for file_path in required_files:
            full_path = self.root / file_path
            self.assertTrue(
                full_path.exists(),
                f"Required file missing: {file_path}"
            )


class TestImportSystem(unittest.TestCase):
    """Test that core imports work"""
    
    def test_configuration_import(self):
        """Test configuration module"""
        try:
            from configuration.settings import settings
            self.assertIsNotNone(settings)
        except ImportError as e:
            self.fail(f"Configuration import failed: {e}")
            
    def test_automation_import(self):
        """Test automation module"""
        try:
            from automation.agent_orchestrator import AgentOrchestrator
            self.assertIsNotNone(AgentOrchestrator)
        except ImportError as e:
            self.fail(f"Automation import failed: {e}")
            
    def test_wake_word_import(self):
        """Test wake word detector"""
        try:
            from models.audio.wake_word.detector import WakeWordDetector
            self.assertIsNotNone(WakeWordDetector)
        except ImportError as e:
            self.fail(f"Wake word import failed: {e}")


class TestVersioning(unittest.TestCase):
    """Test versioning system"""
    
    def setUp(self):
        self.root = Path(__file__).parent.parent
        
    def test_version_file_exists(self):
        """Test VERSION file"""
        version_file = self.root / 'VERSION'
        self.assertTrue(version_file.exists())
        
        with open(version_file, 'r') as f:
            version = f.read().strip()
            
        parts = version.split('.')
        self.assertEqual(len(parts), 3, "Version should be MAJOR.MINOR.PATCH")
        
    def test_version_module(self):
        """Test __version__.py module"""
        try:
            import __version__
            self.assertTrue(hasattr(__version__, '__version__'))
            version = __version__.__version__
            self.assertRegex(version, r'^\d+\.\d+\.\d+$')
        except ImportError as e:
            self.fail(f"Version module import failed: {e}")


def run_all_tests():
    """Run all tests and generate report"""
    print("=" * 70)
    print("🤖 JARVIS PROTOCOL - SYSTEM INTEGRITY TEST")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDirectoryStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestCriticalFiles))
    suite.addTests(loader.loadTestsFromTestCase(TestImportSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestVersioning))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ ALL SYSTEMS OPERATIONAL - JARVIS PROTOCOL ACTIVE")
    else:
        print("⚠️  SYSTEM INTEGRITY COMPROMISED - REVIEW REQUIRED")
    print("=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
