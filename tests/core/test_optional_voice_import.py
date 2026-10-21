"""Text server startup must not depend on optional speech packages."""
import subprocess
import sys


def test_server_imports_without_numpy():
    result = subprocess.run(
        [sys.executable, "-c", """
import builtins
original_import = builtins.__import__
def without_numpy(name, *args, **kwargs):
    if name == 'numpy' or name.startswith('numpy.'):
        raise ModuleNotFoundError('numpy is unavailable for text-only installation')
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_numpy
import atulya.server
"""],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
