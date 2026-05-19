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

from atulya.core.npdna.config import CONFIGS
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
    
    # Check if there's any active run history that got orphaned
    status = _read_train_status() or {}
    metrics = _latest_metric_status()
    
    return {
        "owned_running": owned_running,
        "external_running": len(external) > 0,
        "external": external,
        "status": status,
        "metrics": metrics,
    }


@router.get("/api/train-log")
def api_train_log(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {
        "status": _read_train_status(),
        "log_tail": _tail_text(OUTPUTS_DIR / "train.log", 120),
    }


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
        bench_file.unlink()
    status_file = OUTPUTS_DIR / "train_status.json"
    if status_file.exists():
        status_file.unlink()
        
    cmd = [
        sys.executable,
        str(_ROOT / "training" / "npdna_train.py"),
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
        cmd.extend(["--resume", str(resume)])
        
    log_path = OUTPUTS_DIR / "train.log"
    log_f = log_path.open("a", encoding="utf-8")
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
            await asyncio.sleep(0.2)
            vm = psutil.virtual_memory()
            await ws.send_json({
                "type": "sys",
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
                for line in f.readlines():
                    if line.strip():
                        await ws.send_json({"type": "metric", "data": json.loads(line)})
                last_pos = f.tell()
            if log_f.exists():
                with open(log_f, encoding="utf-8", errors="replace") as f:
                    f.seek(log_pos)
                    for line in f.readlines():
                        if line.strip():
                            await ws.send_json({"type": "log", "data": line.strip()})
                    log_pos = f.tell()
            # Check if training ended
            if DashboardState.TRAIN_PROC and DashboardState.TRAIN_PROC.poll() is not None:
                await ws.send_json({"type": "train_done"})
                DashboardState.TRAIN_PROC = None
    except WebSocketDisconnect:
        pass
