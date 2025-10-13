"""
Atulya Tantra - Deep System Analysis and Testing
Comprehensive issue detection and performance analysis
"""

import unittest
import sys
import os
import importlib
import traceback
from pathlib import Path
from typing import List, Dict, Any
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class DeepAnalyzer:
    """Deep system analyzer for comprehensive issue detection"""
    
    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.issues = []
        self.warnings = []
        self.info = []
    
    def analyze_structure(self) -> Dict[str, Any]:
        """Analyze repository structure"""
        print("\n📁 Analyzing Repository Structure...")
        
        required_dirs = {
            'core': 'Core utilities and base components',
            'configuration': 'Global configuration and settings',
            'protocols': 'JARVIS and SKYNET protocol implementations',
            'protocols/jarvis': 'JARVIS Protocol modules',
            'protocols/skynet': 'SKYNET Protocol modules',
            'models': 'AI model implementations',
            'automation': 'Automation and orchestration',
            'testing': 'Test suites',
            'webui': 'Web interface',
        }
        
        structure_ok = True
        for dir_path, description in required_dirs.items():
            full_path = self.root / dir_path
            if full_path.exists():
                self.info.append(f"✅ {dir_path} - {description}")
            else:
                self.issues.append(f"❌ Missing: {dir_path} - {description}")
                structure_ok = False
        
        return {'status': 'passed' if structure_ok else 'failed'}
    
    def analyze_init_files(self) -> Dict[str, Any]:
        """Check for __init__.py files"""
        print("\n📦 Analyzing Python Package Structure...")
        
        python_dirs = []
        for path in self.root.rglob('*.py'):
            parent = path.parent
            if parent not in python_dirs and parent.name not in ['__pycache__', '.git']:
                python_dirs.append(parent)
        
        init_ok = True
        for dir_path in python_dirs:
            init_file = dir_path / '__init__.py'
            if init_file.exists():
                self.info.append(f"✅ {dir_path.relative_to(self.root)}/__init__.py")
            else:
                if dir_path != self.root:  # Root doesn't need __init__.py
                    self.warnings.append(f"⚠️  Missing: {dir_path.relative_to(self.root)}/__init__.py")
        
        return {'status': 'passed'}
    
    def analyze_imports(self) -> Dict[str, Any]:
        """Test critical imports"""
        print("\n🔌 Analyzing Import System...")
        
        critical_modules = [
            'configuration.settings',
            'configuration.prompts',
            'core.logger',
            'core.exceptions',
            'core.utils',
            'protocols.jarvis',
            'protocols.skynet',
        ]
        
        import_ok = True
        for module_name in critical_modules:
            try:
                importlib.import_module(module_name)
                self.info.append(f"✅ Import successful: {module_name}")
            except Exception as e:
                self.issues.append(f"❌ Import failed: {module_name} - {str(e)}")
                import_ok = False
        
        return {'status': 'passed' if import_ok else 'failed'}
    
    def analyze_configuration(self) -> Dict[str, Any]:
        """Analyze configuration system"""
        print("\n⚙️  Analyzing Configuration System...")
        
        try:
            from configuration import settings, get_prompt, list_available_prompts
            
            # Check settings
            self.info.append(f"✅ Settings loaded: {settings.app_name}")
            self.info.append(f"✅ Default model: {settings.default_model}")
            
            # Check prompts
            prompts = list_available_prompts()
            self.info.append(f"✅ Available prompts: {len(prompts)}")
            
            # Test prompt retrieval
            jarvis_prompt = get_prompt('jarvis')
            if jarvis_prompt:
                self.info.append("✅ JARVIS prompt loaded successfully")
            
            return {'status': 'passed'}
        except Exception as e:
            self.issues.append(f"❌ Configuration error: {str(e)}")
            return {'status': 'failed'}
    
    def analyze_protocols(self) -> Dict[str, Any]:
        """Analyze protocol implementations"""
        print("\n🤖 Analyzing Protocol Systems...")
        
        try:
            # Test JARVIS
            from protocols.jarvis import JarvisInterface
            jarvis = JarvisInterface()
            self.info.append("✅ JARVIS Protocol loaded successfully")
            
            # Test SKYNET
            from protocols.skynet import SkynetOrchestrator
            skynet = SkynetOrchestrator()
            self.info.append("✅ SKYNET Protocol loaded successfully")
            
            return {'status': 'passed'}
        except Exception as e:
            self.issues.append(f"❌ Protocol error: {str(e)}")
            return {'status': 'failed'}
    
    def analyze_dependencies(self) -> Dict[str, Any]:
        """Check dependencies"""
        print("\n📚 Analyzing Dependencies...")
        
        optional_deps = {
            'fastapi': 'Web server framework',
            'ollama': 'AI model interface',
            'edge_tts': 'Text-to-speech',
            'speech_recognition': 'Voice recognition',
        }
        
        for module, description in optional_deps.items():
            try:
                importlib.import_module(module)
                self.info.append(f"✅ {module} - {description}")
            except ImportError:
                self.warnings.append(f"⚠️  Optional: {module} - {description}")
        
        return {'status': 'passed'}
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Basic performance analysis"""
        print("\n⚡ Analyzing Performance...")
        
        # Test import times
        modules_to_test = ['configuration', 'core.logger', 'protocols.jarvis']
        
        for module in modules_to_test:
            start = time.time()
            try:
                importlib.import_module(module)
                elapsed = (time.time() - start) * 1000
                
                if elapsed < 100:
                    self.info.append(f"✅ {module}: {elapsed:.2f}ms (fast)")
                elif elapsed < 500:
                    self.warnings.append(f"⚠️  {module}: {elapsed:.2f}ms (acceptable)")
                else:
                    self.issues.append(f"❌ {module}: {elapsed:.2f}ms (slow)")
            except Exception as e:
                self.issues.append(f"❌ {module}: Import failed")
        
        return {'status': 'passed'}
    
    def run_analysis(self) -> Dict[str, Any]:
        """Run complete deep analysis"""
        print("=" * 70)
        print("🔍 ATULYA TANTRA - DEEP SYSTEM ANALYSIS")
        print("=" * 70)
        
        results = {}
        
        # Run all analyses
        results['structure'] = self.analyze_structure()
        results['init_files'] = self.analyze_init_files()
        results['imports'] = self.analyze_imports()
        results['configuration'] = self.analyze_configuration()
        results['protocols'] = self.analyze_protocols()
        results['dependencies'] = self.analyze_dependencies()
        results['performance'] = self.analyze_performance()
        
        # Print report
        self.print_report(results)
        
        return results
    
    def print_report(self, results: Dict[str, Any]):
        """Print analysis report"""
        print("\n" + "=" * 70)
        print("📊 ANALYSIS REPORT")
        print("=" * 70)
        
        # Summary
        total_tests = len(results)
        passed = sum(1 for r in results.values() if r['status'] == 'passed')
        
        print(f"\n✅ Tests Passed: {passed}/{total_tests}")
        print(f"❌ Tests Failed: {total_tests - passed}/{total_tests}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"ℹ️  Info Messages: {len(self.info)}")
        
        # Issues
        if self.issues:
            print("\n🔴 CRITICAL ISSUES:")
            for issue in self.issues:
                print(f"  {issue}")
        
        # Warnings
        if self.warnings:
            print("\n🟡 WARNINGS:")
            for warning in self.warnings[:10]:  # Show first 10
                print(f"  {warning}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more")
        
        # Overall status
        print("\n" + "=" * 70)
        if not self.issues:
            print("✅ SYSTEM STATUS: OPERATIONAL")
            print("All critical components are functioning correctly.")
        else:
            print("⚠️  SYSTEM STATUS: ISSUES DETECTED")
            print(f"Found {len(self.issues)} critical issues that need attention.")
        print("=" * 70)


class TestDeepAnalysis(unittest.TestCase):
    """Test class for deep analysis"""
    
    def test_deep_analysis(self):
        """Run deep analysis as a test"""
        analyzer = DeepAnalyzer()
        results = analyzer.run_analysis()
        
        # Check for critical failures
        failed_tests = [name for name, result in results.items() 
                       if result['status'] == 'failed']
        
        self.assertEqual(len(failed_tests), 0, 
                        f"Critical tests failed: {', '.join(failed_tests)}")


def run_deep_analysis():
    """Run deep analysis"""
    analyzer = DeepAnalyzer()
    results = analyzer.run_analysis()
    
    # Return success if no critical issues
    return len(analyzer.issues) == 0


if __name__ == '__main__':
    success = run_deep_analysis()
    sys.exit(0 if success else 1)

