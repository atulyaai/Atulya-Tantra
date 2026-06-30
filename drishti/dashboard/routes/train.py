from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, Header

from drishti.dashboard.helpers import (
    _dataset_index,
    _latest_metrics_path,
    _pid_running,
    _python_executable,
    _read_status_file,
    _require_admin,
    _tail_lines,
)
from drishti.dashboard.state import DashboardState, OUTPUTS_DIR

from drishti.dashboard.routes.ws import broadcast_training, broadcast_telemetry, broadcast_event

router = APIRouter()

PID_FILE = OUTPUTS_DIR / "train.pid"
LOG_FILE = OUTPUTS_DIR / "training.log"
METRICS_WINDOW = 500


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _write_pid(pid: int) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid), encoding="utf-8")


def _write_identity_dataset(path: Path) -> Path:
    from atulya.identity import Identity

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in Identity().format_for_training():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def _materialize_all_datasets(datasets: dict[str, Path]) -> Path:
    all_datasets_file = OUTPUTS_DIR / "dashboard_all_datasets.jsonl"
    identity_dataset_file = OUTPUTS_DIR / "dashboard_identity_dataset.jsonl"
    sources = [path for path in datasets.values() if path.suffix.lower() == ".jsonl"]
    if not sources:
        return _write_identity_dataset(identity_dataset_file)

    all_datasets_file.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with all_datasets_file.open("w", encoding="utf-8") as output:
        for source in sources:
            with source.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
                    rows_written += 1
    if rows_written == 0:
        return _write_identity_dataset(identity_dataset_file)
    return all_datasets_file


def _resolve_training_data_path(data_id: str, datasets: dict[str, Path]) -> Path | None:
    if data_id == "all":
        return _materialize_all_datasets(datasets)

    data_path = datasets.get(data_id)
    if data_path and data_path.suffix.lower() == ".json":
        return _write_identity_dataset(OUTPUTS_DIR / "dashboard_identity_dataset.jsonl")
    return data_path


@router.get("/api/training-metrics")
def api_training_metrics(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    metrics_file = OUTPUTS_DIR / "live_metrics.jsonl"
    if not metrics_file.exists():
        metrics_file = _latest_metrics_path() or metrics_file
    metrics = []
    if metrics_file.exists():
        for line in _tail_lines(metrics_file, max_lines=METRICS_WINDOW):
            if line.strip():
                try:
                    metrics.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return {"metrics": metrics, "path": str(metrics_file)}


@router.get("/api/training-status")
def api_training_status(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    pid = _read_pid()
    running = _pid_running(pid)
    status = _read_status_file()
    phase = status.get("phase") or status.get("status") or ("running" if running else "idle")
    log_tail = _tail_lines(LOG_FILE, max_lines=120)

    if not running and phase in {"running", "training"}:
        phase = "stopped"
    status = {**status, "phase": phase}

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast_training(status), loop=loop)
    except Exception:
        pass

    return {
        "running": running,
        "pid": pid,
        "phase": phase,
        "status": status,
        "last": status.get("last") or status.get("last_metric") or status,
        "log_tail": log_tail,
        "log_path": str(LOG_FILE),
        "train_python": _python_executable(),
    }


@router.post("/api/train/start")
def api_train_start(body: dict, _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    existing_pid = _read_pid()
    if _pid_running(existing_pid):
        return {"error": f"Training is already running with PID {existing_pid}", "pid": existing_pid}

    config = str(body.get("config") or "atulya_small")
    steps = max(1, min(int(body.get("steps") or 50), int(os.environ.get("ATULYA_DASHBOARD_MAX_STEPS", "50000"))))
    lr = float(body.get("lr") or 5e-4)
    seq_limit = max(8, min(int(body.get("seq_limit") or 128), 4096))
    checkpoint_every = max(0, int(body.get("checkpoint_every") or 0))
    device = str(body.get("device") or "cpu")
    if device == "auto":
        device = "cpu"

    datasets = _dataset_index()
    data_id = str(body.get("data_id") or body.get("dataset") or "all")
    data_path = _resolve_training_data_path(data_id, datasets)
    if data_path is None:
        return {"error": "No dataset found in tantra/training/datasets"}
    if not data_path.exists():
        return {"error": f"Dataset file not found: {data_path}"}

    cmd = [
        _python_executable(),
        "-m",
        "tantra.training.npdna_train",
        "--config",
        config,
        "--steps",
        str(steps),
        "--lr",
        str(lr),
        "--output",
        str(OUTPUTS_DIR),
        "--data",
        str(data_path),
        "--seq-limit",
        str(seq_limit),
        "--checkpoint-every",
        str(checkpoint_every),
        "--device",
        device,
    ]
    if body.get("pack"):
        cmd.append("--pack")
    resume_id = str(body.get("resume_id") or "")
    if resume_id and resume_id != "fresh":
        from drishti.dashboard.helpers import _checkpoint_index

        resume_path = _checkpoint_index().get(resume_id)
        if resume_path:
            cmd.extend(["--resume", str(resume_path)])

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast_event("Training Started", f"PID {_python_executable()} training with config {config}", "info"))
    except Exception:
        pass

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("ab") as log:
        log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] START {' '.join(cmd)}\n".encode("utf-8"))
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parents[4]),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    DashboardState.TRAIN_PROCESS = proc
    _write_pid(proc.pid)
    return {"ok": True, "pid": proc.pid, "cmd": cmd, "log_path": str(LOG_FILE), "data_path": str(data_path)}


@router.post("/api/train/stop")
def api_train_stop(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    pid = _read_pid()
    if not _pid_running(pid):
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(broadcast_event("Training Stopped", "No process was running", "warning"))
        except Exception:
            pass
        return {"ok": True, "running": False, "message": "No training process is running"}
    if os.name == "nt":
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"])
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast_event("Training Stopped", f"PID {pid} was stopped", "warning"))
    except Exception:
        pass
    return {"ok": True, "running": False, "stopped_pid": pid}
