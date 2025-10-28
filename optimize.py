#!/usr/bin/env python3
"""
Atulya Tantra AGI - Automated Code Optimizer
Automatically optimizes code, removes unnecessary files, and improves performance
"""

import os
import sys
import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Set
import subprocess

class CodeOptimizer:
    """Automated code optimization and cleanup"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.optimizations_applied = []
        self.files_processed = 0
        
    def remove_unnecessary_files(self) -> int:
        """Remove unnecessary files and directories"""
        print("🧹 Removing unnecessary files...")
        
        unnecessary_patterns = [
            "*.pyc",
            "__pycache__",
            "*.pyo",
            "*.pyd",
            ".pytest_cache",
            ".coverage",
            "htmlcov",
            ".mypy_cache",
            ".ruff_cache",
            "*.log",
            "*.tmp",
            ".DS_Store",
            "Thumbs.db"
        ]
        
        removed_count = 0
        
        for pattern in unnecessary_patterns:
            for file_path in self.project_root.rglob(pattern):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        removed_count += 1
                        print(f"✅ Removed: {file_path.relative_to(self.project_root)}")
                    elif file_path.is_dir():
                        import shutil
                        shutil.rmtree(file_path)
                        removed_count += 1
                        print(f"✅ Removed directory: {file_path.relative_to(self.project_root)}")
                except Exception as e:
                    print(f"⚠️ Could not remove {file_path}: {e}")
        
        return removed_count
    
    def optimize_imports(self, file_path: Path) -> bool:
        """Optimize imports in a Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Remove unused imports
            tree = ast.parse(content)
            used_names = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    used_names.add(node.attr)
            
            lines = content.split('\n')
            optimized_lines = []
            
            for line in lines:
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    # Check if import is used
                    import_match = re.match(r'(?:from\s+\S+\s+)?import\s+(.+)', line.strip())
                    if import_match:
                        imports = import_match.group(1).split(',')
                        used_imports = []
                        
                        for imp in imports:
                            imp = imp.strip()
                            if ' as ' in imp:
                                alias = imp.split(' as ')[1].strip()
                                if alias in used_names:
                                    used_imports.append(imp)
                            else:
                                if imp in used_names:
                                    used_imports.append(imp)
                        
                        if used_imports:
                            if line.strip().startswith('from '):
                                prefix = line.strip().split(' import ')[0] + ' import '
                                optimized_lines.append(prefix + ', '.join(used_imports))
                            else:
                                optimized_lines.append('import ' + ', '.join(used_imports))
                    else:
                        optimized_lines.append(line)
                else:
                    optimized_lines.append(line)
            
            optimized_content = '\n'.join(optimized_lines)
            
            if optimized_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(optimized_content)
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error optimizing imports in {file_path}: {e}")
            return False
    
    def remove_empty_lines(self, file_path: Path) -> bool:
        """Remove excessive empty lines"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Remove multiple consecutive empty lines
            content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
            
            # Remove empty lines at the beginning and end
            content = content.strip() + '\n'
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error removing empty lines in {file_path}: {e}")
            return False
    
    def add_type_hints(self, file_path: Path) -> bool:
        """Add basic type hints to functions"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Simple type hint additions for common patterns
            patterns = [
                (r'def (\w+)\(self\):', r'def \1(self) -> None:'),
                (r'def (\w+)\(self, (\w+)\):', r'def \1(self, \2: str) -> None:'),
                (r'def (\w+)\(self, (\w+), (\w+)\):', r'def \1(self, \2: str, \3: str) -> None:'),
            ]
            
            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error adding type hints in {file_path}: {e}")
            return False
    
    def optimize_python_file(self, file_path: Path) -> Dict[str, bool]:
        """Optimize a single Python file"""
        optimizations = {
            'imports': False,
            'empty_lines': False,
            'type_hints': False
        }
        
        try:
            # Skip if not a Python file
            if file_path.suffix != '.py':
                return optimizations
            
            # Skip __init__.py files
            if file_path.name == '__init__.py':
                return optimizations
            
            print(f"🔧 Optimizing: {file_path.relative_to(self.project_root)}")
            
            # Apply optimizations
            optimizations['imports'] = self.optimize_imports(file_path)
            optimizations['empty_lines'] = self.remove_empty_lines(file_path)
            optimizations['type_hints'] = self.add_type_hints(file_path)
            
            self.files_processed += 1
            
        except Exception as e:
            print(f"❌ Error optimizing {file_path}: {e}")
        
        return optimizations
    
    def optimize_all_python_files(self) -> Dict[str, int]:
        """Optimize all Python files in the project"""
        print("🔧 Optimizing Python files...")
        
        stats = {
            'files_processed': 0,
            'imports_optimized': 0,
            'empty_lines_removed': 0,
            'type_hints_added': 0
        }
        
        # Find all Python files
        python_files = list(self.project_root.rglob("*.py"))
        
        for file_path in python_files:
            # Skip certain directories
            if any(skip_dir in str(file_path) for skip_dir in ['venv', '__pycache__', '.git']):
                continue
            
            optimizations = self.optimize_python_file(file_path)
            
            if optimizations['imports']:
                stats['imports_optimized'] += 1
            if optimizations['empty_lines']:
                stats['empty_lines_removed'] += 1
            if optimizations['type_hints']:
                stats['type_hints_added'] += 1
            
            stats['files_processed'] += 1
        
        return stats
    
    def create_optimized_requirements(self) -> bool:
        """Create optimized requirements.txt"""
        print("📦 Creating optimized requirements.txt...")
        
        try:
            # Essential dependencies only
            essential_deps = [
                "fastapi==0.109.0",
                "uvicorn[standard]==0.27.0",
                "pydantic==2.5.3",
                "sqlalchemy==2.0.25",
                "requests==2.31.0",
                "openai==1.30.1",
                "anthropic==0.27.0",
                "ollama==0.2.0",
                "SpeechRecognition==3.10.0",
                "pyttsx3==2.90",
                "psutil==5.9.7",
                "python-dotenv==1.0.0",
                "pytest==7.4.4"
            ]
            
            requirements_file = self.project_root / "requirements.txt"
            
            with open(requirements_file, 'w') as f:
                f.write("# Atulya Tantra AGI - Essential Dependencies\n")
                f.write("# Optimized for performance and minimal footprint\n\n")
                for dep in essential_deps:
                    f.write(f"{dep}\n")
            
            print("✅ Optimized requirements.txt created")
            return True
            
        except Exception as e:
            print(f"❌ Error creating optimized requirements: {e}")
            return False
    
    def create_auto_config(self) -> bool:
        """Create automatic configuration"""
        print("⚙️ Creating automatic configuration...")
        
        try:
            config = {
                "auto_setup": True,
                "auto_optimize": True,
                "auto_test": True,
                "performance_mode": True,
                "minimal_deps": True,
                "ai_provider": "ollama",
                "features": {
                    "voice": True,
                    "autonomous": False,
                    "streaming": True
                }
            }
            
            config_file = self.project_root / "auto_config.json"
            
            import json
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Automatic configuration created")
            return True
            
        except Exception as e:
            print(f"❌ Error creating auto config: {e}")
            return False
    
    def run_code_formatting(self) -> bool:
        """Run automatic code formatting"""
        print("🎨 Running code formatting...")
        
        try:
            # Try to install and run black
            subprocess.run([sys.executable, "-m", "pip", "install", "black"], 
                         check=True, capture_output=True)
            
            # Format Core directory
            result = subprocess.run([sys.executable, "-m", "black", "Core/"], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Code formatted with Black")
                return True
            else:
                print(f"⚠️ Black formatting had issues: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error running code formatting: {e}")
            return False
    
    def run_full_optimization(self) -> bool:
        """Run complete code optimization"""
        print("🚀 Starting automated code optimization...")
        print("=" * 60)
        
        # Remove unnecessary files
        removed_files = self.remove_unnecessary_files()
        print(f"✅ Removed {removed_files} unnecessary files")
        
        # Optimize Python files
        stats = self.optimize_all_python_files()
        print(f"✅ Processed {stats['files_processed']} Python files")
        print(f"✅ Optimized imports in {stats['imports_optimized']} files")
        print(f"✅ Removed empty lines in {stats['empty_lines_removed']} files")
        print(f"✅ Added type hints to {stats['type_hints_added']} files")
        
        # Create optimized requirements
        self.create_optimized_requirements()
        
        # Create auto configuration
        self.create_auto_config()
        
        # Run code formatting
        self.run_code_formatting()
        
        print("\n" + "=" * 60)
        print("🎉 Code optimization completed!")
        print(f"📊 Total optimizations applied: {len(self.optimizations_applied)}")
        
        return True

def main():
    """Main entry point"""
    project_root = Path(__file__).parent
    
    optimizer = CodeOptimizer(project_root)
    success = optimizer.run_full_optimization()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
