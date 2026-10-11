"""Install missing Atulya packages and prepare local speech recognition before launch."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
MEDIAPIPE_VERSION = "1.1.0"
MEDIAPIPE_PACKAGE_URL = (
    "https://registry.npmjs.org/@mediapipe/tasks-vision/-/"
    f"tasks-vision-{MEDIAPIPE_VERSION}.tgz"
)
GESTURE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/1/gesture_recognizer.task"
)
GESTURE_MODEL_SHA256 = "97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482"
MEDIAPIPE_FILES = (
    "LICENSE",
    "NOTICE.md",
    "vision_bundle.mjs",
    "wasm/vision_wasm_internal.js",
    "wasm/vision_wasm_internal.wasm",
    "wasm/vision_wasm_module_internal.js",
    "wasm/vision_wasm_module_internal.wasm",
    "wasm/vision_wasm_nosimd_internal.js",
    "wasm/vision_wasm_nosimd_internal.wasm",
)
MEDIAPIPE_FILE_SHA256 = {
    "LICENSE": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    "NOTICE.md": "075f6a4c1eebbc0a56cb53c0711dea2fac8e20d66cb35085481cb4d83b3183b4",
    "vision_bundle.mjs": "9d5fc9ef74b22329cf9aa88dc543956d192b8c254210b187271614713eb5b10c",
    "wasm/vision_wasm_internal.js": "7c652617b5bef832f42878ce8c5f752b0724bca6054e4bc1013a37d4b1949723",
    "wasm/vision_wasm_internal.wasm": "782eda3ec1f414fdb4f1d66a8b59093eb4d5ab437e06117796abf05962d68eef",
    "wasm/vision_wasm_module_internal.js": "70eff3956521b7de058d7173a4935c95e4a223c26ea624b9f5a936d3a043dcb0",
    "wasm/vision_wasm_module_internal.wasm": "ee03b14a878e6c3c053a1bfa62e166dc45244be54dc0bbe61c578f710b771f6a",
    "wasm/vision_wasm_nosimd_internal.js": "510fc70a170eb8b46767a7abab2af89a7a8341fa5b3ebfb8a5de41a79b7fa9df",
    "wasm/vision_wasm_nosimd_internal.wasm": "b802041d105876865d6a0806f2ff7c4419a7f1b80bc01340fe36e759c2030011",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(
    url: str,
    destination: Path,
    *,
    expected_sha256: str = "",
    expected_sha512: str = "",
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size == 0:
            raise OSError("The downloaded asset was empty.")
        verified = bool(expected_sha256 and _sha256(temporary) == expected_sha256)
        if expected_sha512:
            digest = hashlib.sha512()
            with temporary.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            verified = base64.b64encode(digest.digest()).decode("ascii") == expected_sha512
        if not verified:
            raise OSError("The downloaded asset failed its integrity check.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_gesture_assets() -> bool:
    """Install the pinned browser recognizer and model into project-local folders."""
    runtime = PROJECT_ROOT / "models" / "runtime" / "mediapipe"
    model = PROJECT_ROOT / "models" / "gesture" / "gesture_recognizer.task"
    files_ready = all(
        (runtime / name).is_file()
        and _sha256(runtime / name) == MEDIAPIPE_FILE_SHA256[name]
        for name in MEDIAPIPE_FILES
    )
    if not files_ready:
        print(f"Preparing local gesture recognition runtime (MediaPipe {MEDIAPIPE_VERSION})…", flush=True)
        try:
            with tempfile.TemporaryDirectory(prefix="atulya-mediapipe-") as staging:
                archive_path = Path(staging) / "tasks-vision.tgz"
                # The versioned npm registry metadata supplies the published
                # SRI digest; verify the tarball before extracting any members.
                metadata_url = f"https://registry.npmjs.org/@mediapipe/tasks-vision/{MEDIAPIPE_VERSION}"
                with urlopen(metadata_url, timeout=30) as response:
                    metadata = json.load(response)
                integrity = str(metadata.get("dist", {}).get("integrity", ""))
                if metadata.get("version") != MEDIAPIPE_VERSION or not integrity.startswith("sha512-"):
                    raise OSError("The pinned MediaPipe package has no valid SHA-512 registry integrity value.")
                _download(
                    MEDIAPIPE_PACKAGE_URL,
                    archive_path,
                    expected_sha512=integrity.removeprefix("sha512-"),
                )
                runtime.mkdir(parents=True, exist_ok=True)
                with tarfile.open(archive_path, "r:gz") as archive:
                    for relative in MEDIAPIPE_FILES:
                        member_name = f"package/{relative}"
                        member = archive.getmember(member_name)
                        extracted = archive.extractfile(member)
                        if extracted is None:
                            raise OSError(f"MediaPipe package file is missing: {relative}")
                        destination = runtime / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        payload = extracted.read()
                        if hashlib.sha256(payload).hexdigest() != MEDIAPIPE_FILE_SHA256[relative]:
                            raise OSError(f"MediaPipe package file failed integrity verification: {relative}")
                        destination.write_bytes(payload)
        except (OSError, tarfile.TarError, KeyError) as exc:
            print(f"Gesture runtime setup could not finish; the rest of Atulya will still start: {exc}", file=sys.stderr)
            return False

    if not model.is_file() or _sha256(model) != GESTURE_MODEL_SHA256:
        print("Preparing the local gesture recognition model under models/gesture/…", flush=True)
        try:
            _download(GESTURE_MODEL_URL, model, expected_sha256=GESTURE_MODEL_SHA256)
        except OSError as exc:
            print(f"Gesture model setup could not finish; the rest of Atulya will still start: {exc}", file=sys.stderr)
            return False
    return True


def prepare_tts_model(models_dir: Path) -> bool:
    """Prepare only the pinned local Supertonic model files under models/."""
    from tools.plugins.voice.tts import TTS_MODEL_FILE_SHA256, TTS_MODEL_FOLDER, model_assets_ready

    if model_assets_ready(models_dir):
        return True
    destination = models_dir / "voice" / "tts" / "supertonic-3-int8" / TTS_MODEL_FOLDER
    url = (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
        f"{TTS_MODEL_FOLDER}.tar.bz2"
    )
    print("Preparing the local Hindi/English speech model under models/voice/tts/…", flush=True)
    try:
        models_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="atulya-tts-", dir=models_dir) as staging:
            stage = Path(staging)
            archive_path = stage / "supertonic.tar.bz2"
            with urlopen(url, timeout=120) as response, archive_path.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            ready_files: dict[str, Path] = {}
            with tarfile.open(archive_path, "r:bz2") as archive:
                for filename, expected_digest in TTS_MODEL_FILE_SHA256.items():
                    member = archive.getmember(f"{TTS_MODEL_FOLDER}/{filename}")
                    if not member.isfile():
                        raise OSError(f"Speech model entry is not a regular file: {filename}")
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise OSError(f"Speech model file is missing: {filename}")
                    staged_file = stage / filename
                    digest = hashlib.sha256()
                    with extracted, staged_file.open("wb") as output:
                        while chunk := extracted.read(1024 * 1024):
                            digest.update(chunk)
                            output.write(chunk)
                    if digest.hexdigest() != expected_digest:
                        raise OSError(f"Speech model file failed its SHA-256 check: {filename}")
                    ready_files[filename] = staged_file
            destination.mkdir(parents=True, exist_ok=True)
            for filename, staged_file in ready_files.items():
                staged_file.replace(destination / filename)
    except (OSError, tarfile.TarError, KeyError) as exc:
        print(f"Local speech output setup could not finish; browser speech remains available: {exc}", file=sys.stderr)
        return False
    return model_assets_ready(models_dir)


def main() -> int:
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required.", file=sys.stderr)
        return 1

    required = {
        "fastapi": "fastapi",
        "httpx": "httpx",
        "pydantic": "pydantic",
        "dotenv": "python-dotenv",
        "uvicorn": "uvicorn",
        "faster_whisper": "faster-whisper",
        "sherpa_onnx": "sherpa-onnx",
        "multipart": "python-multipart",
        "mcp": "mcp",
    }
    missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
    try:
        pip_version = tuple(int(part) for part in version("pip").split(".")[:2])
    except (PackageNotFoundError, ValueError):
        pip_version = (0, 0)
    if pip_version < (26, 2):
        missing.append("secure pip (>=26.2,<27)")
    try:
        av_major = int(version("av").split(".", 1)[0])
    except (PackageNotFoundError, ValueError):
        av_major = 0
    if av_major >= 19:
        missing.append("compatible PyAV (<19)")
    if missing:
        print(f"Installing missing Atulya packages: {', '.join(missing)}", flush=True)
        try:
            if pip_version < (26, 2):
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "pip>=26.2,<27"],
                    check=True,
                    cwd=PROJECT_ROOT,
                )
            lock_file = PROJECT_ROOT / "requirements.lock.txt"
            if not lock_file.is_file():
                raise FileNotFoundError("requirements.lock.txt is missing; restore the project dependency lock and retry.")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(lock_file)],
                check=True,
                cwd=PROJECT_ROOT,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"Atulya setup failed while installing packages: {exc}", file=sys.stderr)
            return 1

    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env", override=False)
        from atulya.settings import Settings
        from tools.plugins.voice.setup import prepare_models
        from tools.plugins.brain.local_llm import prepare_local_model

        settings = Settings.from_environment()
        prepare_models(
            settings.models_dir,
            stt_model=os.environ.get("ATULYA_STT_MODEL", "base").strip() or "base",
        )
        prepare_tts_model(settings.models_dir)
        from tools.hardware import detect

        hardware = detect()
        print(f"Detected {hardware.summary()}", flush=True)
        if settings.model_provider == "local" or (settings.model_provider_auto and hardware.can_run_local_model):
            prepare_local_model(settings.models_dir)
        elif settings.model_provider_auto:
            print("Skipping the offline chat model: this computer has under 6 GB RAM. "
                  "Add a cloud provider key in .env for chat.", flush=True)
        prepare_gesture_assets()
    except Exception as exc:
        print(f"Atulya setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
