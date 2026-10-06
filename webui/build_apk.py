import shutil
import subprocess
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANDROID = ROOT / "android"


def apply_version(gradle_file: Path, version: str) -> None:
    """Set the native APK version from Python's authoritative package version."""
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Expected a three-part numeric release version, got {version!r}")
    code = int(parts[0]) * 1_000_000 + int(parts[1]) * 1_000 + int(parts[2])
    text = gradle_file.read_text(encoding="utf-8")
    text, code_count = re.subn(r"(?m)^(\s*)versionCode\s+\d+\s*$", rf"\g<1>versionCode {code}", text, count=1)
    text, name_count = re.subn(r"(?m)^(\s*)versionName\s+['\"][^'\"]*['\"]\s*$",
                               rf'\g<1>versionName "{version}"', text, count=1)
    if code_count != 1 or name_count != 1:
        raise ValueError("Could not find versionCode/versionName in the generated Android app Gradle file")
    gradle_file.write_text(text, encoding="utf-8")


def run(*command: str) -> None:
    """Run a webui tool, resolving the Windows .CMD shims for npm and npx.

    subprocess in list form will not find ``npm``/``npx`` on their own there --
    they are ``npm.cmd``/``npx.cmd`` -- so resolve the real path first.
    """
    executable = shutil.which(command[0]) or command[0]
    subprocess.run([executable, *command[1:]], cwd=ROOT, check=True)


def build_web() -> None:
    """Put a current web bundle in ``dist/`` before Capacitor copies it over.

    ``dist/`` is gitignored, so a checkout has none. Syncing an absent or stale
    one is how an APK ends up with no UI in it at all, and nothing else in the
    pipeline -- local or on the runner -- builds it.
    """
    if not (ROOT / "node_modules").exists():
        run("npm", "ci")
    run("npm", "run", "build")


def main() -> None:
    version_source = (ROOT.parent / "atulya" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', version_source, re.MULTILINE)
    if not match:
        raise ValueError("atulya.__version__ is missing")
    version = match.group(1)
    build_web()
    if not ANDROID.exists():
        run("npx", "cap", "add", "android")
    run("npx", "cap", "sync", "android")
    shutil.copy2(ROOT / "android_manifest.xml", ANDROID / "app" / "src" / "main" / "AndroidManifest.xml")
    shutil.copy2(ROOT / "android_gradle.properties", ANDROID / "gradle.properties")
    apply_version(ANDROID / "app" / "build.gradle", version)
    gradle = ANDROID / ("gradlew.bat" if __import__("os").name == "nt" else "gradlew")
    subprocess.run([str(gradle), "assembleDebug"], cwd=ANDROID, check=True)
    print(ANDROID / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk")


if __name__ == "__main__":
    main()
