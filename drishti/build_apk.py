import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANDROID = ROOT / "android"


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    if not ANDROID.exists():
        run("npx", "cap", "add", "android")
    run("npx", "cap", "sync", "android")
    shutil.copy2(ROOT / "android_manifest.xml", ANDROID / "app" / "src" / "main" / "AndroidManifest.xml")
    shutil.copy2(ROOT / "android_gradle.properties", ANDROID / "gradle.properties")
    gradle = ANDROID / ("gradlew.bat" if __import__("os").name == "nt" else "gradlew")
    subprocess.run([str(gradle), "assembleDebug"], cwd=ANDROID, check=True)
    print(ANDROID / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk")


if __name__ == "__main__":
    main()
