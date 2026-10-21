"""Exercise the real deploy script with failed functional checks, without a server."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required for Linux deployment script")
def test_failed_functional_selftest_rolls_back_even_when_health_passes(project_temp_dir):
    project = project_temp_dir / "Atulya-Tantra"
    (project / "data").mkdir(parents=True)
    (project / ".venv/bin").mkdir(parents=True)
    python = project / ".venv/bin/python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o700)
    source = Path("tools/deploy_server.sh").resolve()
    harness = '''
git() {
 case "$*" in
  'rev-parse HEAD') echo old ;;
  'rev-parse origin/main') echo new ;;
  'reset -q --hard old') echo rollback >> "$HOME/trace" ;;
 esac
 return 0
}
sudo() { return 0; }
curl() { return 0; }
timeout() { return 1; }
seq() { echo 1; }
. "$1"
'''
    result = subprocess.run([shutil.which("sh"), "-c", harness, "test", str(source)],
                            env=dict(os.environ, HOME=str(project_temp_dir)), capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert "functional selftest failed" in result.stderr
    assert (project_temp_dir / "trace").read_text().strip() == "rollback"
