"""NP-DNA Dashboard Training Routes.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
import psutil
from fastapi import APIRouter, Header, Request, WebSocket, WebSocketDisconnect

from tantra.core.npdna.config import CONFIGS
from atulya.dashboard.state import (
    _ROOT,
    OUTPUTS_DIR,
    DashboardState,
    MAX_STEPS,
    MAX_LIMIT,
    MAX_SEQ_LIMIT,
)
from atulya.dashboard.helpers import (
    _require_admin,
    _check_request_origin,
    _check_ws_origin,
    _read_train_status,
    _tail_text,
    _training_processes,
    _dataset_index,
    _is_within,
    _dashboard_roots,
    _auto_config_name,
    _clamp_int,
    _clamp_float,
    _checkpoint_index,
    _append_run_history,
    _stop_training,
    _latest_metric_status,
)

logger = logging.getLogger("atulya.dashboard.routes.train")
router = APIRouter()


@router.get("/api/training-status")
def api_training_status(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    owned_running = DashboardState.TRAIN_PROC is not None and DashboardState.TRAIN_PROC.poll() is None
    external = _training_processes()

    status = _read_train_status() or {}
    metrics = _latest_metric_status()
    is_running = owned_running or len(external) > 0

    if status and not is_running:
        phase = str(status.get("phase") or "").lower()
        terminal_phases = ("complete", "done", "finished", "error", "stopped", "blocked")
        is_terminal = any(phase.endswith(t) for t in terminal_phases)
        if not is_terminal:
            status = {
                **status,
                "stale": True,
                "message": "No active training process found; this is the last saved status from an interrupted run.",
            }

    return {
        "running": is_running,
        "owned_running": owned_running,
        "external_running": len(external) > 0,
        "external": external,
        "status": status,
        "metrics": metrics,
        "last": metrics.get("last") or status,
        "log_tail": _tail_text(OUTPUTS_DIR / "train.log", 120) if is_running else [],
    }


@router.get("/api/train-log")
def api_train_log(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {
        "status": _read_train_status(),
        "log_tail": _tail_text(OUTPUTS_DIR / "train.log", 120),
    }


@router.get("/api/training-metrics")
def api_training_metrics(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    points = []
    if mf.exists():
        try:
            with mf.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        points.append(json.loads(line))
        except Exception as e:
            logger.error("Failed to read live_metrics.jsonl: %s", e)
    return {"metrics": points[-500:]}


@router.post("/api/train/start")
def api_train_start(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    if DashboardState.TRAIN_PROC and DashboardState.TRAIN_PROC.poll() is None:
        return {"error": "Training already running. Stop first."}
        
    external_training = _training_processes()
    if external_training:
        return {
            "error": "Training process already running outside this dashboard session. Stop it before starting another run.",
            "external": external_training,
        }
        
    data_id = str(body.get("data_id") or body.get("data_path") or "")
    data_path = _dataset_index().get(data_id)
    if not data_path:
        candidate = Path(data_id)
        if candidate.exists() and _is_within(candidate, _dashboard_roots()):
            data_path = candidate.resolve()
            
    if not data_path:
        return {"error": "Dataset not found or not allowed"}
        
    config = str(body.get("config", _auto_config_name()))
    if config not in CONFIGS:
        return {"error": f"Unknown config: {config}"}
        
    steps = _clamp_int(body.get("steps"), 1000, 1, MAX_STEPS)
    limit = _clamp_int(body.get("limit"), 10000, 1, MAX_LIMIT)
    checkpoint_every = _clamp_int(body.get("checkpoint_every"), 0, 0, max(1000, MAX_STEPS))
    lr = _clamp_float(body.get("lr"), 5e-4, 1e-6, 1.0)
    seq_limit = _clamp_int(body.get("seq_limit"), 128, 32, MAX_SEQ_LIMIT)
    
    # Clear old live metrics
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    mf.parent.mkdir(parents=True, exist_ok=True)
    if mf.exists():
        mf.unlink()
    bench_file = OUTPUTS_DIR / "benchmark.json"
    if bench_file.exists():
        bak_file = OUTPUTS_DIR / "benchmark.json.bak"
        try:
            if bak_file.exists():
                bak_file.unlink()
            bench_file.rename(bak_file)
        except Exception:
            try:
                bench_file.unlink()
            except Exception:
                pass
    status_file = OUTPUTS_DIR / "train_status.json"
    if status_file.exists():
        status_file.unlink()
    stop_signal = OUTPUTS_DIR / "stop_signal.txt"
    if stop_signal.exists():
        try:
            stop_signal.unlink()
        except Exception:
            pass
        
    cmd = [
        sys.executable,
        "-m",
        "atulya.training.npdna_train",
        "--config",
        config,
        "--steps",
        str(steps),
        "--lr",
        str(lr),
        "--data",
        str(data_path),
        "--limit",
        str(limit),
        "--log-every",
        "5",
        "--seq-limit",
        str(seq_limit),
        "--checkpoint-every",
        str(checkpoint_every),
        "--device",
        "auto",
        "--bpe-merges",
        str(_clamp_int(body.get("bpe_merges"), 2000, 0, 16000)),
        "--bpe-max-words",
        str(_clamp_int(body.get("bpe_max_words"), 0, 0, 50000)),
        "--min-free-ram-gb",
        str(_clamp_float(body.get("min_free_ram_gb"), 1.5, 0.5, 16.0)),
        "--balance-weight",
        str(_clamp_float(body.get("balance_weight"), 0.05, 0.0, 1.0)),
        "--plasticity-interval",
        str(_clamp_int(body.get("plasticity_interval"), max(10, steps // 40), 10, max(10, steps))),
        "--plasticity-overload-threshold",
        str(_clamp_float(body.get("plasticity_overload_threshold"), 0.14, 0.05, 0.8)),
        "--plasticity-dead-threshold",
        str(_clamp_float(body.get("plasticity_dead_threshold"), 0.01, 0.0, 0.2)),
        "--plasticity-grow-cooldown",
        str(_clamp_int(body.get("plasticity_grow_cooldown"), 1, 0, 20)),
        "--lr-schedule",
        "cosine",
    ]
    if body.get("bf16", False):
        cmd.append("--bf16")
    if body.get("pack", True):
        cmd.append("--pack")

    # Advanced training flags
    if body.get("rag", False):
        cmd.append("--rag")
    if body.get("lora", False):
        cmd.extend(["--lora-rank", str(_clamp_int(body.get("lora_rank"), 8, 1, 64))])
        cmd.extend(["--lora-alpha", str(_clamp_float(body.get("lora_alpha"), 16.0, 1.0, 128.0))])
    if body.get("rlhf", False):
        cmd.append("--rlhf")
    if body.get("auto_vocab", True):
        cmd.append("--auto-vocab")
    if body.get("checkpoint_save", True):
        cmd.append("--save-checkpoints")
        
    resume_id = body.get("resume_id")
    if resume_id is None:
        resume_id = body.get("resume_from")
        
    if resume_id in ("", "fresh", "none"):
        resume_id = None
    elif resume_id is None and (OUTPUTS_DIR / "metadata.json").exists():
        resume_id = "latest"
        
    if resume_id:
        resume = _checkpoint_index().get(str(resume_id))
        if not resume:
            return {"error": "Resume checkpoint not found or not allowed"}
        meta_path = Path(resume) / "metadata.json"
        if meta_path.exists():
            try:
                resume_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                requested_cfg = CONFIGS[config]
                resume_hidden = int(resume_meta.get("hidden_size") or 0)
                resume_layers = int(resume_meta.get("num_layers") or 0)
                if resume_hidden and resume_layers and (
                    resume_hidden != int(requested_cfg.hidden_size)
                    or resume_layers != int(requested_cfg.num_layers)
                ):
                    return {
                        "error": (
                            f"Resume checkpoint shape does not match config '{config}'. "
                            "Choose a matching checkpoint or use '-- Initialize New Instance --' for fresh training."
                        ),
                        "resume": str(resume_id),
                        "resume_hidden_size": resume_hidden,
                        "resume_layers": resume_layers,
                        "requested_hidden_size": requested_cfg.hidden_size,
                        "requested_layers": requested_cfg.num_layers,
                    }
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                return {"error": "Resume checkpoint metadata could not be read"}
        cmd.extend(["--resume", str(resume)])
        
    log_path = OUTPUTS_DIR / "train.log"
    log_f = log_path.open("a", encoding="utf-8")
    DashboardState.TRAIN_LOG_F = log_f
    DashboardState.TRAIN_PROC = subprocess.Popen(
        cmd,
        cwd=str(_ROOT),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    
    _append_run_history({
        "event": "started",
        "pid": DashboardState.TRAIN_PROC.pid,
        "config": config,
        "steps": steps,
        "limit": limit,
        "seq_limit": seq_limit,
        "dataset": data_path.name,
        "resume": str(resume_id) if resume_id else "fresh",
    })
    return {"status": "started", "pid": DashboardState.TRAIN_PROC.pid}


@router.post("/api/train/stop")
def api_train_stop(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    stopped = _stop_training()
    if stopped:
        return {"status": "stopped", "stopped": stopped}
    return {"status": "not_running"}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if not _check_ws_origin(ws):
        await ws.close(code=4003)
        return
    await ws.accept()
    log_f = OUTPUTS_DIR / "train.log"
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    last_pos, log_pos = 0, 0

    # Seek to end of existing files initially
    if mf.exists():
        last_pos = mf.stat().st_size
    if log_f.exists():
        log_pos = log_f.stat().st_size

    try:
        while True:
            await asyncio.sleep(0.5)
            is_training = DashboardState.TRAIN_PROC is not None and DashboardState.TRAIN_PROC.poll() is None
            vm = psutil.virtual_memory()
            await ws.send_json({
                "type": "system",
                "data": {
                    "ram_total_gb": round(vm.total / 1e9, 1),
                    "ram_avail_gb": round(vm.available / 1e9, 1),
                    "cpu_pct": psutil.cpu_percent(interval=0),
                },
            })
            status = _read_train_status()
            if status:
                await ws.send_json({"type": "status", "data": status})
            if not mf.exists():
                continue
            with open(mf, encoding="utf-8") as f:
                f.seek(last_pos)
                chunk = f.read()
                if chunk:
                    decoder = json.JSONDecoder()
                    pos = 0
                    while pos < len(chunk):
                        while pos < len(chunk) and chunk[pos] in ' \t\r\n':
                            pos += 1
                        if pos >= len(chunk):
                            break
                        try:
                            obj, end = decoder.raw_decode(chunk, pos)
                            await ws.send_json({"type": "metric", "data": obj})
                            pos += end
                        except json.JSONDecodeError:
                            break
                last_pos = f.tell()
            if log_f.exists():
                with open(log_f, encoding="utf-8", errors="replace") as f:
                    f.seek(log_pos)
                    for line in f.readlines():
                        if line.strip():
                            await ws.send_json({"type": "log", "data": line.strip()})
                    log_pos = f.tell()
            if DashboardState.TRAIN_PROC and DashboardState.TRAIN_PROC.poll() is not None:
                final_status = _read_train_status()
                if final_status:
                    await ws.send_json({"type": "status", "data": final_status})
                await ws.send_json({"type": "train_done"})
                # Restore benchmark from backup if present and target is missing
                bak_bench = OUTPUTS_DIR / "benchmark.json.bak"
                target_bench = OUTPUTS_DIR / "benchmark.json"
                if bak_bench.exists() and not target_bench.exists():
                    try:
                        import shutil
                        shutil.copy2(bak_bench, target_bench)
                    except Exception:
                        pass
                DashboardState.TRAIN_PROC = None
    except WebSocketDisconnect:
        pass
