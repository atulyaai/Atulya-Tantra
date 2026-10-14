#!/usr/bin/env python3
"""
Atulya Proactive Health Monitor & Auto-Fixer

This system:
1. Monitors the running Atulya instance for issues
2. Detects common problems (gesture/vision conflicts, missing models, etc.)
3. Automatically fixes issues or provides actionable guidance
4. Reports health status via webhook/log

Run as a cron job or systemd timer: */5 * * * * /path/to/proactive_monitor.py
"""

import asyncio
import json
import logging
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import subprocess
import hashlib

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(PROJECT_ROOT / "data" / "logs" / "proactive_monitor.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("proactive_monitor")

class HealthCheck:
    def __init__(self, name: str, check_fn, fix_fn=None, severity="warning"):
        self.name = name
        self.check_fn = check_fn
        self.fix_fn = fix_fn
        self.severity = severity  # info, warning, error, critical

class ProactiveMonitor:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.data_dir = project_root / "data"
        self.logs_dir = self.data_dir / "logs"
        self.models_dir = project_root / "models"
        self.webui_dir = project_root / "webui"
        
        self.checks: List[HealthCheck] = []
        self.results: Dict = {}
        self._register_checks()
    
    def _register_checks(self):
        """Register all health checks"""
        
        # 1. MediaPipe runtime files
        self.checks.append(HealthCheck(
            "mediapipe_runtime",
            self._check_mediapipe_runtime,
            self._fix_mediapipe_runtime,
            "error"
        ))
        
        # 2. Gesture model
        self.checks.append(HealthCheck(
            "gesture_model",
            self._check_gesture_model,
            self._fix_gesture_model,
            "error"
        ))
        
        # 3. Vision model (mmproj)
        self.checks.append(HealthCheck(
            "vision_model",
            self._check_vision_model,
            self._fix_vision_model,
            "warning"
        ))
        
        # 4. WebUI files integrity
        self.checks.append(HealthCheck(
            "webui_integrity",
            self._check_webui_integrity,
            None,
            "warning"
        ))
        
        # 5. Python environment
        self.checks.append(HealthCheck(
            "python_env",
            self._check_python_env,
            self._fix_python_env,
            "warning"
        ))
        
        # 6. Disk space
        self.checks.append(HealthCheck(
            "disk_space",
            self._check_disk_space,
            None,
            "warning"
        ))
        
        # 7. Service health (if running locally)
        self.checks.append(HealthCheck(
            "service_health",
            self._check_service_health,
            None,
            "info"
        ))
        
        # 8. Config validity
        self.checks.append(HealthCheck(
            "config_validity",
            self._check_config,
            None,
            "warning"
        ))
        
        # 9. Core file protection
        self.checks.append(HealthCheck(
            "core_protection",
            self._check_core_protection,
            self._fix_core_protection,
            "info"
        ))
        
        # 10. Log rotation
        self.checks.append(HealthCheck(
            "log_rotation",
            self._check_log_rotation,
            self._fix_log_rotation,
            "info"
        ))
    
    # ===== CHECK FUNCTIONS =====
    
    def _check_mediapipe_runtime(self) -> Dict:
        """Check MediaPipe runtime files exist and are valid"""
        runtime_dir = self.models_dir / "runtime" / "mediapipe"
        required = [
            "vision_bundle.mjs",
            "wasm/vision_wasm_internal.js",
            "wasm/vision_wasm_internal.wasm",
            "wasm/vision_wasm_module_internal.js",
            "wasm/vision_wasm_module_internal.wasm",
            "wasm/vision_wasm_nosimd_internal.js",
            "wasm/vision_wasm_nosimd_internal.wasm",
        ]
        
        missing = []
        for f in required:
            if not (runtime_dir / f).exists():
                missing.append(f)
        
        return {
            "ok": len(missing) == 0,
            "missing": missing,
            "runtime_dir": str(runtime_dir)
        }
    
    def _fix_mediapipe_runtime(self) -> bool:
        """Download missing MediaPipe runtime files"""
        log.info("Downloading MediaPipe runtime files...")
        try:
            result = subprocess.run([
                sys.executable, "-c", """
import hashlib, json, tarfile, tempfile, base64
from pathlib import Path
from urllib.request import urlopen

VERSION = "1.1.0"
URL = f"https://registry.npmjs.org/@mediapipe/tasks-vision/-/tasks-vision-{VERSION}.tgz"
FILES = [
    "vision_bundle.mjs",
    "wasm/vision_wasm_internal.js",
    "wasm/vision_wasm_internal.wasm",
    "wasm/vision_wasm_module_internal.js", 
    "wasm/vision_wasm_module_internal.wasm",
    "wasm/vision_wasm_nosimd_internal.js",
    "wasm/vision_wasm_nosimd_internal.wasm",
]
SHA256 = {
    "vision_bundle.mjs": "9d5fc9ef74b22329cf9aa88dc543956d192b8c254210b187271614713eb5b10c",
    "wasm/vision_wasm_internal.js": "7c652617b5bef832f42878ce8c5f752b0724bca6054e4bc1013a37d4b1949723",
    "wasm/vision_wasm_internal.wasm": "782eda3ec1f414fdb4f1d66a8b59093eb4d5ab437e06117796abf05962d68eef",
    "wasm/vision_wasm_module_internal.js": "70eff3956521b7de058d7173a4935c95e4a223c26ea624b9f5a936d3a043dcb0",
    "wasm/vision_wasm_module_internal.wasm": "ee03b14a878e6c3c053a1bfa62e166dc45244be54dc0bbe61c578f710b771f6a",
    "wasm/vision_wasm_nosimd_internal.js": "510fc70a170eb8b46767a7abab2af89a7a8341fa5b3ebfb8a5de41a79b7fa9df",
    "wasm/vision_wasm_nosimd_internal.wasm": "b802041d105876865d6a0806f2ff7c4419a7f1b80bc01340fe36e759c2030011",
}

runtime = Path("/home/ubuntu/Atulya-Tantra/models/runtime/mediapipe")

# Get integrity
with urlopen(f"https://registry.npmjs.org/@mediapipe/tasks-vision/{VERSION}", timeout=30) as r:
    meta = json.load(r)
integrity = meta.get("dist", {}).get("integrity", "")

with tempfile.TemporaryDirectory(prefix="mediapipe-") as staging:
    archive = Path(staging) / "tasks-vision.tgz"
    with urlopen(URL, timeout=120) as r:
        archive.write_bytes(r.read())
    # Verify sha512
    digest = hashlib.sha512()
    with archive.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            digest.update(chunk)
    if base64.b64encode(digest.digest()).decode() != integrity.removeprefix("sha512-"):
        raise ValueError("Integrity check failed")
    with tarfile.open(archive, "r:gz") as tar:
        for rel in FILES:
            member = tar.getmember(f"package/{rel}")
            payload = tar.extractfile(member).read()
            if hashlib.sha256(payload).hexdigest() != SHA256[rel]:
                raise ValueError(f"SHA256 mismatch: {rel}")
            dest = runtime / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            print(f"  OK {rel}")

print("MediaPipe runtime restored")
"""
            ], capture_output=True, text=True, timeout=300, cwd=self.project_root)
            
            if result.returncode == 0:
                log.info("MediaPipe runtime restored successfully")
                return True
            else:
                log.error(f"Failed to restore MediaPipe: {result.stderr}")
                return False
        except Exception as e:
            log.error(f"Error fixing MediaPipe: {e}")
            return False
    
    def _check_gesture_model(self) -> Dict:
        """Check gesture recognition model"""
        model_path = self.models_dir / "gesture" / "gesture_recognizer.task"
        expected_sha256 = "97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482"
        
        if not model_path.exists():
            return {"ok": False, "error": "Model file missing", "path": str(model_path)}
        
        # Verify hash
        h = hashlib.sha256()
        with model_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        
        if h.hexdigest() != expected_sha256:
            return {"ok": False, "error": "Model hash mismatch (corrupted)", "path": str(model_path)}
        
        return {"ok": True, "path": str(model_path), "size": model_path.stat().st_size}
    
    def _fix_gesture_model(self) -> bool:
        """Download gesture model"""
        log.info("Downloading gesture model...")
        try:
            result = subprocess.run([
                sys.executable, "-c", """
import hashlib
from pathlib import Path
from urllib.request import urlopen

URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
SHA256 = "97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482"
DEST = Path("/home/ubuntu/Atulya-Tantra/models/gesture/gesture_recognizer.task")

DEST.parent.mkdir(parents=True, exist_ok=True)
with urlopen(URL, timeout=120) as r:
    DEST.write_bytes(r.read())

h = hashlib.sha256(DEST.read_bytes()).hexdigest()
if h != SHA256:
    DEST.unlink()
    raise ValueError(f"Hash mismatch: {h}")
print("Gesture model restored")
"""
            ], capture_output=True, text=True, timeout=120, cwd=self.project_root)
            
            return result.returncode == 0
        except Exception as e:
            log.error(f"Error fixing gesture model: {e}")
            return False
    
    def _check_vision_model(self) -> Dict:
        """Check vision model (mmproj)"""
        model_path = self.models_dir / "vision" / "mmproj-Qwen_Qwen3.5-2B-bf16.gguf"
        
        if not model_path.exists():
            return {"ok": False, "error": "Vision model missing", "path": str(model_path)}
        
        return {"ok": True, "path": str(model_path), "size": model_path.stat().st_size}
    
    def _fix_vision_model(self) -> bool:
        """Vision model fix - just log, user needs to download manually"""
        log.warning("Vision model missing - user needs to download mmproj-Qwen_Qwen3.5-2B-bf16.gguf to models/vision/")
        return False  # Can't auto-fix
    
    def _check_webui_integrity(self) -> Dict:
        """Check key WebUI files exist"""
        key_files = [
            "webui/assistant.js",
            "webui/renderer.js",
            "webui/renderer.css",
            "webui/index.html",
        ]
        
        missing = []
        for f in key_files:
            if not (self.project_root / f).exists():
                missing.append(f)
        
        return {"ok": len(missing) == 0, "missing": missing}
    
    def _check_python_env(self) -> Dict:
        """Check Python virtual environment"""
        venv_python = self.project_root / ".venv" / "bin" / "python"
        if not venv_python.exists():
            return {"ok": False, "error": "Virtual environment missing"}
        
        # Check key packages
        try:
            result = subprocess.run([str(venv_python), "-c", "import fastapi, pydantic; print('OK')"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return {"ok": False, "error": f"Missing packages: {result.stderr}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        
        return {"ok": True}
    
    def _fix_python_env(self) -> bool:
        """Recreate virtual environment"""
        log.warning("Environment repair is disabled: setup files and dependencies are protected.")
        return False
    
    def _check_disk_space(self) -> Dict:
        """Check disk space"""
        usage = shutil.disk_usage(self.project_root)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_pct = usage.used / usage.total * 100
        
        return {
            "ok": free_gb > 2.0,  # At least 2GB free
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "used_pct": round(used_pct, 1)
        }
    
    def _check_service_health(self) -> Dict:
        """Check if Atulya service is running and healthy"""
        try:
            import requests
            # Try local endpoint
            resp = requests.get("http://localhost:8501/api/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {"ok": True, "health": data}
        except Exception:
            pass
        
        # Check if process is running
        try:
            result = subprocess.run(["pgrep", "-f", "atulya.cli"], capture_output=True, text=True)
            if result.returncode == 0:
                return {"ok": True, "pid": result.stdout.strip(), "note": "Process running but HTTP not responding"}
        except Exception:
            pass
        
        return {"ok": False, "error": "Service not running or not responding"}
    
    def _check_config(self) -> Dict:
        """Check configuration validity"""
        env_file = self.project_root / ".env"
        if not env_file.exists():
            return {"ok": False, "error": ".env file missing"}
        
        # Check required settings
        required = ["ATULYA_BRAIN", "ATULYA_VAULT_PASSPHRASE"]
        missing = []
        content = env_file.read_text()
        for req in required:
            if f"{req}=" not in content or f"{req}=" in content and content.split(f"{req}=")[1].split("\n")[0].strip() == "":
                missing.append(req)
        
        return {"ok": len(missing) == 0, "missing": missing}
    
    def _check_core_protection(self) -> Dict:
        """Check core file protection status"""
        lock_file = self.project_root / ".core_locked"
        manifest_file = self.project_root / ".core_manifest.json"
        
        return {
            "ok": lock_file.exists() and manifest_file.exists(),
            "locked": lock_file.exists(),
            "manifest_exists": manifest_file.exists()
        }
    
    def _fix_core_protection(self) -> bool:
        """Re-initialize core protection"""
        log.warning("Core permission and hook changes are disabled.")
        return False
    
    def _check_log_rotation(self) -> Dict:
        """Check log files aren't too large"""
        large_logs = []
        for log_file in self.logs_dir.glob("*.log"):
            size_mb = log_file.stat().st_size / (1024**2)
            if size_mb > 100:  # > 100MB
                large_logs.append({"file": log_file.name, "size_mb": round(size_mb, 1)})
        
        return {"ok": len(large_logs) == 0, "large_logs": large_logs}
    
    def _fix_log_rotation(self) -> bool:
        """Rotate large log files"""
        rotated = 0
        for log_file in self.logs_dir.glob("*.log"):
            size_mb = log_file.stat().st_size / (1024**2)
            if size_mb > 100:
                # Rotate: move to .1, .2, etc.
                for i in range(5, 0, -1):
                    old = self.logs_dir / f"{log_file.name}.{i}"
                    new = self.logs_dir / f"{log_file.name}.{i+1}"
                    if old.exists():
                        old.rename(new)
                log_file.rename(self.logs_dir / f"{log_file.name}.1")
                log_file.touch()
                rotated += 1
                log.info(f"Rotated {log_file.name}")
        
        return rotated > 0
    
    # ===== MAIN RUNNER =====
    
    async def run_checks(self, auto_fix: bool = False) -> Dict:
        """Run all health checks"""
        log.info("Starting proactive health check...")
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {},
            "summary": {"ok": 0, "warning": 0, "error": 0, "critical": 0, "fixed": 0}
        }
        
        for check in self.checks:
            log.debug(f"Running check: {check.name}")
            try:
                result = check.check_fn()
                result["severity"] = check.severity
                results["checks"][check.name] = result
                
                if result.get("ok", False):
                    results["summary"]["ok"] += 1
                    log.debug(f"  {check.name}: OK")
                else:
                    severity = check.severity
                    results["summary"][severity] = results["summary"].get(severity, 0) + 1
                    log.warning(f"  {check.name}: FAILED - {result}")
                    
                    # Attempt auto-fix
                    if auto_fix and check.fix_fn and check.name in {"mediapipe_runtime", "gesture_model"}:
                        log.info(f"  Attempting auto-fix for {check.name}...")
                        try:
                            fixed = check.fix_fn()
                            if fixed:
                                results["summary"]["fixed"] += 1
                                log.info(f"  {check.name}: AUTO-FIXED")
                                # Re-run check
                                result = check.check_fn()
                                result["severity"] = check.severity
                                results["checks"][check.name] = result
                                if result.get("ok", False):
                                    results["summary"]["ok"] += 1
                                    results["summary"][severity] -= 1
                        except Exception as e:
                            log.error(f"  Auto-fix failed for {check.name}: {e}")
                            
            except Exception as e:
                log.error(f"Check {check.name} raised exception: {e}")
                results["checks"][check.name] = {"ok": False, "error": str(e), "severity": "error"}
                results["summary"]["error"] += 1
        
        # Save results
        results_file = self.logs_dir / "health_check_results.json"
        results_file.write_text(json.dumps(results, indent=2))
        
        # Log summary
        s = results["summary"]
        log.info(f"Health check complete: OK={s['ok']} WARN={s.get('warning',0)} ERROR={s.get('error',0)} CRIT={s.get('critical',0)} FIXED={s['fixed']}")
        
        return results
    
    def generate_report(self, results: Dict) -> str:
        """Generate human-readable report"""
        lines = [
            "=" * 60,
            "ATULYA PROACTIVE HEALTH REPORT",
            f"Time: {results['timestamp']}",
            "=" * 60,
            "",
            f"Summary: OK={results['summary']['ok']} "
            f"WARN={results['summary'].get('warning',0)} "
            f"ERROR={results['summary'].get('error',0)} "
            f"CRIT={results['summary'].get('critical',0)} "
            f"FIXED={results['summary']['fixed']}",
            "",
        ]
        
        for name, result in results["checks"].items():
            status = "✓" if result.get("ok") else "✗"
            severity = result.get("severity", "info").upper()
            lines.append(f"  {status} [{severity}] {name}")
            if not result.get("ok"):
                if "error" in result:
                    lines.append(f"      Error: {result['error']}")
                if "missing" in result:
                    lines.append(f"      Missing: {', '.join(result['missing'])}")
        
        return "\n".join(lines)


async def main():
    monitor = ProactiveMonitor(PROJECT_ROOT)
    
    # Run checks with auto-fix
    results = await monitor.run_checks(auto_fix=False)
    
    # Print report
    print(monitor.generate_report(results))
    
    # Exit with error code if critical issues remain
    if results["summary"].get("critical", 0) > 0 or results["summary"].get("error", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
