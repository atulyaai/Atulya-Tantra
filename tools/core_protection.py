#!/usr/bin/env python3
"""
Atulya Core File Protection System

This script makes core files immutable while keeping workspace files editable.
It uses git to track core files and prevent accidental modifications.

Usage:
  python3 tools/core_protection.py --init      # Initialize protection
  python3 tools/core_protection.py --check     # Check for violations
  python3 tools/core_protection.py --lock      # Lock core files (make immutable)
  python3 tools/core_protection.py --unlock    # Unlock for maintenance
  python3 tools/core_protection.py --status    # Show protection status
"""

import os
import sys
import subprocess
from pathlib import Path

# Core files that should be protected (immutable)
CORE_FILES = [
    # Main application
    "atulya/server.py",
    "atulya/auth.py",
    "atulya/cli.py",
    "atulya/settings.py",
    "atulya/history.py",
    "atulya/persona.py",
    "atulya/profiles.py",
    "atulya/push.py",
    "atulya/secrets_store.py",
    "atulya/logging_setup.py",
    "atulya/dbrepair.py",
    "atulya/__init__.py",
    
    # WebUI core files
    "webui/assistant.js",
    "webui/renderer.js",
    "webui/renderer.css",
    "webui/index.html",
    "webui/api.js",
    "webui/webcam.js",
    "webui/styles.css",
    "webui/main.jsx",
    "webui/Orb.jsx",
    "webui/Panel.jsx",
    "webui/Providers.jsx",
    "webui/Reflexes.jsx",
    "webui/Routines.jsx",
    "webui/Senses.jsx",
    "webui/Dashboard.jsx",
    "webui/AboutYou.jsx",
    "webui/MemoryTree.jsx",
    "webui/Hologram.js",
    "webui/sections.js",
    "webui/Pairing.jsx",
    "webui/sw.js",
    "webui/vite.config.js",
    "webui/package.json",
    "webui/package-lock.json",
    
    # Bootstrap and setup
    "tools/bootstrap.py",
    "tools/plugins/__init__.py",
    "tools/plugins/voice/__init__.py",
    "tools/plugins/voice/tts.py",
    "tools/plugins/voice/stt.py",
    "requirements.lock.txt",
    "requirements-dev.lock.txt",
    "pyproject.toml",
    
    # Config
    ".env.example",
    "Dockerfile",
    "install.sh",
    "install.ps1",
    "start.sh",
    "start.bat",
]

# Workspace files that should remain editable
WORKSPACE_PATTERNS = [
    "*.log",
    "data/**/*",
    "models/**/*",
    ".venv/**/*",
    "__pycache__/**/*",
    "node_modules/**/*",
    "dist/**/*",
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.backup",
    "webui/webui/**/*",  # Duplicate/experimental
    ".git/**/*",
    "tests/**/*",
    "docs/**/*",
    "android/**/*",
    "agents/**/*",
    "*.md",  # Documentation
    "CLAUDE.md",
    "README.md",
]

class CoreProtection:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.core_files = [project_root / f for f in CORE_FILES if (project_root / f).exists()]
        self.lock_file = project_root / ".core_locked"
        self.manifest_file = project_root / ".core_manifest.json"
    
    def get_file_hash(self, filepath: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def init(self):
        """Initialize the protection system"""
        print("Initializing core file protection...")
        
        # Create manifest with current hashes
        import json
        manifest = {
            "version": 1,
            "files": {}
        }
        
        for f in self.core_files:
            if f.exists():
                manifest["files"][str(f.relative_to(self.project_root))] = {
                    "hash": self.get_file_hash(f),
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime
                }
        
        self.manifest_file.write_text(json.dumps(manifest, indent=2))
        print(f"Manifest created with {len(manifest['files'])} core files")
        
        # Create .gitattributes for git-based protection
        gitattributes = self.project_root / ".gitattributes"
        attrs = []
        for f in CORE_FILES:
            attrs.append(f"{f} linguist-generated=true diff=core")
        attrs.append("* linguist-generated=false")
        gitattributes.write_text("\n".join(attrs) + "\n")
        print(".gitattributes created")
        
        # Create pre-commit hook
        self.create_precommit_hook()
        
        # Lock files
        self.lock()
    
    def create_precommit_hook(self):
        """Create a git pre-commit hook to protect core files"""
        hook = self.project_root / ".git" / "hooks" / "pre-commit"
        if not hook.parent.exists():
            return
        
        hook_content = '''#!/bin/sh
# Atulya Core File Protection - Pre-commit Hook
# Prevents accidental modification of core files

PROTECTED_FILES="''' + " ".join(CORE_FILES) + '''"

echo "Checking core file modifications..."
VIOLATIONS=0

for file in $PROTECTED_FILES; do
    if git diff --cached --name-only | grep -q "^$file$"; then
        echo "ERROR: Core file '$file' is staged for commit!"
        echo "Core files are protected. Use 'git commit --no-verify' to override (not recommended)."
        VIOLATIONS=1
    fi
done

if [ $VIOLATIONS -eq 1 ]; then
    exit 1
fi

exit 0
'''
        hook.write_text(hook_content)
        hook.chmod(0o755)
        print("Pre-commit hook installed")
    
    def lock(self):
        """Make core files immutable (read-only)"""
        if not sys.platform.startswith("win"):
            for f in self.core_files:
                if f.exists():
                    os.chmod(f, 0o444)  # Read-only for all
        else:
            # Windows: use attrib +R
            for f in self.core_files:
                if f.exists():
                    subprocess.run(["attrib", "+R", str(f)], capture_output=True)
        
        self.lock_file.write_text("locked\n")
        print(f"Locked {len(self.core_files)} core files (read-only)")
    
    def unlock(self):
        """Make core files writable for maintenance"""
        if not sys.platform.startswith("win"):
            for f in self.core_files:
                if f.exists():
                    os.chmod(f, 0o644)
        else:
            for f in self.core_files:
                if f.exists():
                    subprocess.run(["attrib", "-R", str(f)], capture_output=True)
        
        if self.lock_file.exists():
            self.lock_file.unlink()
        print(f"Unlocked {len(self.core_files)} core files")
    
    def check(self) -> bool:
        """Check for violations (modified core files)"""
        import json
        
        if not self.manifest_file.exists():
            print("No manifest found. Run --init first.")
            return False
        
        manifest = json.loads(self.manifest_file.read_text())
        violations = []
        
        for rel_path, info in manifest["files"].items():
            f = self.project_root / rel_path
            if not f.exists():
                violations.append(f"{rel_path}: MISSING")
                continue
            
            current_hash = self.get_file_hash(f)
            if current_hash != info["hash"]:
                violations.append(f"{rel_path}: MODIFIED (hash mismatch)")
        
        if violations:
            print("CORE FILE VIOLATIONS DETECTED:")
            for v in violations:
                print(f"  - {v}")
            return False
        else:
            print("All core files intact.")
            return True
    
    def status(self):
        """Show protection status"""
        print("=== Atulya Core Protection Status ===")
        print(f"Project root: {self.project_root}")
        print(f"Core files tracked: {len(self.core_files)}")
        print(f"Locked: {'Yes' if self.lock_file.exists() else 'No'}")
        print(f"Manifest: {'Exists' if self.manifest_file.exists() else 'Missing'}")
        
        if self.manifest_file.exists():
            import json
            manifest = json.loads(self.manifest_file.read_text())
            modified = 0
            missing = 0
            for rel_path, info in manifest["files"].items():
                f = self.project_root / rel_path
                if not f.exists():
                    missing += 1
                elif self.get_file_hash(f) != info["hash"]:
                    modified += 1
            print(f"Modified: {modified}")
            print(f"Missing: {missing}")
        
        # Show workspace files (editable)
        workspace_count = 0
        for pattern in WORKSPACE_PATTERNS:
            for f in self.project_root.glob(pattern):
                if f.is_file():
                    workspace_count += 1
        print(f"Workspace files (editable): ~{workspace_count}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Atulya Core File Protection")
    parser.add_argument("--init", action="store_true", help="Initialize protection")
    parser.add_argument("--check", action="store_true", help="Check for violations")
    parser.add_argument("--lock", action="store_true", help="Lock core files")
    parser.add_argument("--unlock", action="store_true", help="Unlock core files")
    parser.add_argument("--status", action="store_true", help="Show status")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    protection = CoreProtection(project_root)
    
    if args.init:
        protection.init()
    elif args.check:
        if not protection.check():
            sys.exit(1)
    elif args.lock:
        protection.lock()
    elif args.unlock:
        protection.unlock()
    elif args.status:
        protection.status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()