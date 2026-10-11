"""Lifecycle for Atulya's project-local llama.cpp chat model."""
from __future__ import annotations

import os
import json
import hashlib
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


MODEL_REPOSITORY = "bartowski/Qwen_Qwen3.5-2B-GGUF"
MODEL_FILENAME = "Qwen_Qwen3.5-2B-Q4_K_M.gguf"
VISION_FILENAME = "mmproj-Qwen_Qwen3.5-2B-bf16.gguf"
MODEL_ALIAS = "qwen3.5-2b"
MODEL_SHA256 = "57a1085840f497d764a7fc5d346922dbde961efb54cc792ea81d694fd846a1d8"
VISION_SHA256 = "91ea86496a1c02d7cd32fbfa963e103d2a512fa29ca4a22dca1a9c92c3fd30d8"
MODEL_PORT = 11435


def prepare_local_model(models_dir: Path) -> None:
    """Download a compact quantized model and llama.cpp runtime when absent."""
    model_dir = models_dir / "chat"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / MODEL_FILENAME
    vision_dir = models_dir / "vision"
    vision_dir.mkdir(parents=True, exist_ok=True)
    vision_path = vision_dir / VISION_FILENAME
    marker = models_dir / ".chat-ready"
    marker_text = f"{MODEL_FILENAME}\n{MODEL_SHA256}\n{VISION_FILENAME}\n{VISION_SHA256}\n"
    try:
        verified = marker.read_text(encoding="utf-8") == marker_text
    except OSError:
        verified = False
    model_valid = model_path.is_file() and model_path.stat().st_size > 1_000_000_000
    if not model_valid or (not verified and _sha256(model_path) != MODEL_SHA256):
        url = f"https://huggingface.co/{MODEL_REPOSITORY}/resolve/main/{MODEL_FILENAME}"
        print("Downloading the local chat and vision models into models/chat and models/vision (about 2.1 GB total)...", flush=True)
        _download(url, model_path, expected_sha256=MODEL_SHA256)
    vision_valid = vision_path.is_file() and vision_path.stat().st_size > 500_000_000
    if not vision_valid or (not verified and _sha256(vision_path) != VISION_SHA256):
        url = f"https://huggingface.co/{MODEL_REPOSITORY}/resolve/main/{VISION_FILENAME}"
        _download(url, vision_path, expected_sha256=VISION_SHA256)
    marker.write_text(marker_text, encoding="utf-8")
    license_path = model_dir / "LICENSE"
    if not license_path.exists():
        _download("https://huggingface.co/Qwen/Qwen3.5-2B/resolve/main/LICENSE", license_path)

    runtime_dir = models_dir / "runtime" / "llama.cpp"
    server_names = ("llama-server.exe",) if os.name == "nt" else ("llama-server",)
    if any(any(runtime_dir.rglob(name)) for name in server_names):
        return
    archive_url, archive_name = _runtime_asset_url()
    archive_path = runtime_dir.parent / archive_name
    runtime_dir.mkdir(parents=True, exist_ok=True)
    print("Preparing the local chat engine...", flush=True)
    _download(archive_url, archive_path)
    _extract_runtime(archive_path, runtime_dir)
    archive_path.unlink(missing_ok=True)
    if not any(runtime_dir.rglob(name) for name in server_names):
        raise RuntimeError("The local chat engine download did not contain llama-server.")


def _download(url: str, target: Path, *, expected_sha256: str = "") -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    existing = partial.stat().st_size if partial.is_file() else 0
    try:
        headers = {"User-Agent": "Atulya-Tantra/1.0"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            mode = "ab" if existing and response.status == 206 else "wb"
            start = existing if mode == "ab" else 0
            content_range = response.headers.get("Content-Range", "")
            match = re.search(r"/([0-9]+)$", content_range)
            total = int(match.group(1)) if match else start + int(response.headers.get("Content-Length", "0") or 0)
            received = start
            last_percent = -1
            with partial.open(mode) as output:
                if start:
                    print(f"Resuming download at {start / 1_000_000:.0f} MB.", flush=True)
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    received += len(chunk)
                    if total:
                        percent = int(received * 100 / total)
                        if percent != last_percent:
                            print(f"\r  {percent}%", end="", flush=True)
                            last_percent = percent
        if total and received != total:
            raise RuntimeError(f"Download was incomplete ({received} of {total} bytes); run start.bat again to resume it.")
        if expected_sha256:
            digest = _sha256(partial)
            if digest != expected_sha256:
                partial.unlink(missing_ok=True)
                raise RuntimeError("The downloaded local chat model failed its SHA-256 integrity check.")
        partial.replace(target)
        if total:
            print()
    except Exception:
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_suffixes() -> list[str]:
    """Release asset suffixes for this OS/CPU, best match first (GPU build, then CPU)."""
    from tools.hardware import detect

    hw = detect()
    if hw.system == "windows":
        names = [f"win-vulkan-{hw.arch}"] if hw.llama_flavor == "vulkan" else []
        names.append(f"win-cpu-{hw.arch}")
    elif hw.system == "macos":
        names = [f"macos-{hw.arch}"]
    else:
        names = [f"ubuntu-vulkan-{hw.arch}"] if hw.llama_flavor == "vulkan" else []
        names.append(f"ubuntu-{hw.arch}")
    return [f"{name}{ext}" for name in names for ext in (".zip", ".tar.gz")]


def _gpu_layers() -> int:
    """Offload all layers when the installed runtime has GPU support; ATULYA_GPU_LAYERS overrides."""
    raw = os.environ.get("ATULYA_GPU_LAYERS", "auto").strip().lower()
    if raw.isdigit():
        return int(raw)
    from tools.hardware import detect

    return 99 if detect().llama_flavor in {"metal", "vulkan"} else 0


def _runtime_asset_url() -> tuple[str, str]:
    request = urllib.request.Request(
        "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=30",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Atulya-Tantra/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        import json
        releases = json.load(response)
    for wanted in _runtime_suffixes():
        for release in releases:
            for asset in release.get("assets", []):
                if asset.get("name", "").endswith(wanted):
                    return asset["browser_download_url"], asset["name"]
    raise RuntimeError("No compatible llama.cpp local chat runtime was found for this computer.")


def _extract_runtime(archive: Path, target: Path) -> None:
    if archive.suffix.lower() == ".zip":
        import zipfile

        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                destination = (target / entry.filename).resolve()
                if target.resolve() not in destination.parents and destination != target.resolve():
                    raise RuntimeError("The local chat runtime archive contains an unsafe path.")
            bundle.extractall(target)
        return
    import tarfile

    with tarfile.open(archive, "r:gz") as bundle:
        for entry in bundle.getmembers():
            destination = (target / entry.name).resolve()
            if target.resolve() not in destination.parents and destination != target.resolve():
                raise RuntimeError("The local chat runtime archive contains an unsafe path.")
        if hasattr(tarfile, "data_filter"):
            bundle.extractall(target, filter="data")
        else:
            for entry in bundle.getmembers():
                if entry.issym() or entry.islnk() or not (entry.isfile() or entry.isdir()):
                    raise RuntimeError("This Python version cannot safely extract links in the local chat runtime archive.")
                destination = (target / entry.name).resolve()
                if target.resolve() not in destination.parents and destination != target.resolve():
                    raise RuntimeError("The local chat runtime archive contains an unsafe path.")
                if entry.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(entry)
                if source is None:
                    raise RuntimeError("The local chat runtime archive contains an unreadable file.")
                with source, destination.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                destination.chmod(entry.mode & 0o777)


class LocalLlamaRuntime:
    """Run one local model server for the lifetime of the Atulya API."""

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        model = self.models_dir / "chat" / MODEL_FILENAME
        runtime = self.models_dir / "runtime" / "llama.cpp"
        executable_name = "llama-server.exe" if os.name == "nt" else "llama-server"
        executable = next(runtime.rglob(executable_name), None)
        if not model.is_file() or executable is None:
            raise RuntimeError("The local chat model is missing. Run start.bat to prepare it automatically.")
        if self._is_existing_local_model_ready():
            # Another Atulya window may already own the shared local model
            # server. Reuse it instead of launching a second process on 11435.
            return
        command = [str(executable), "--model", str(model)]
        projector = self.models_dir / "vision" / VISION_FILENAME
        if projector.is_file():
            command.extend(("--mmproj", str(projector)))
        command.extend([
            "--alias", MODEL_ALIAS,
            "--host", "127.0.0.1", "--port", str(MODEL_PORT), "--ctx-size", "4096",
            "--parallel", "1", "--threads", str(max(2, min((os.cpu_count() or 4) - 1, 8))),
            "--n-gpu-layers", str(_gpu_layers()), "--reasoning-budget", "0", "--jinja",
        ])
        self.process = subprocess.Popen(command, cwd=runtime, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 180
        health_url = f"http://127.0.0.1:{MODEL_PORT}/health"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("The local chat model could not start. Check available memory, then restart Atulya.")
            try:
                with urllib.request.urlopen(health_url, timeout=2) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(0.5)
        self.stop()
        raise RuntimeError("The local chat model took too long to start. Restart Atulya to try again.")

    @staticmethod
    def _is_existing_local_model_ready() -> bool:
        """Reuse an already-running Qwen server, but never mistake another model for it."""
        models_url = f"http://127.0.0.1:{MODEL_PORT}/v1/models"
        try:
            with urllib.request.urlopen(models_url, timeout=2) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, ValueError):
            return False
        models = payload.get("data", []) if isinstance(payload, dict) else []
        return any(
            isinstance(item, dict) and item.get("id") == MODEL_ALIAS
            for item in models
        )

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.process = None
