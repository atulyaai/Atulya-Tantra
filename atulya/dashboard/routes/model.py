"""NP-DNA Dashboard Model Routes.
"""
from __future__ import annotations
import json
import logging
import shutil
import sys
from pathlib import Path
from fastapi import APIRouter, Header, Request, HTTPException

from atulya.dashboard.state import _ROOT, DashboardState
from atulya.dashboard.helpers import (
    _require_admin,
    _check_request_origin,
    _checkpoint_index,
    _read_metadata,
    _benchmark_matches_model,
    _checkpoint_step,
    _model_final_loss,
    _model_best_loss,
    _model_readiness,
    _list_checkpoints,
    _model_registry,
    _read_run_history,
    _dataset_index,
    _dashboard_roots,
    _is_within,
    _clamp_int,
)

logger = logging.getLogger("atulya.dashboard.routes.model")
router = APIRouter()


@router.get("/api/model")
def api_model_info(
    model_id: str = "latest",
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        return {"exists": False}
    meta = _read_metadata(model_path)
    if not meta:
        return {"exists": False}
    
    # Check benchmark file
    bench_file = model_path / "benchmark.json"
    bench_data = None
    if bench_file.exists():
        try:
            bench_data = json.loads(bench_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not _benchmark_matches_model(model_path, bench_data):
        bench_data = None
    
    return {
        "exists": True,
        "config": meta.get("train_config_name") or meta.get("config_name", "?"),
        "step": _checkpoint_step(model_id, meta),
        "loss": _model_final_loss(meta),
        "best_loss": _model_best_loss(meta),
        "params": meta.get("parameter_count", 0),
        "vocab_used": meta.get("vocab_size", 0),
        "vocab_cap": meta.get("vocab_capacity", 0),
        "saved_at": meta.get("saved_at", 0),
        "benchmark": bench_data,
        "readiness": _model_readiness(meta),
    }


@router.get("/api/checkpoints")
def api_checkpoints(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"checkpoints": _list_checkpoints()}


@router.get("/api/models")
def api_models(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"models": _model_registry()}


@router.delete("/api/models/{model_id}")
def api_delete_model(
    model_id: str,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    if model_id == "latest":
        return {"error": "Cannot delete the active 'latest' model directory directly. Use reset."}
    
    model_path = _checkpoint_index().get(model_id)
    if not model_path or not model_path.exists():
        return {"error": "Model not found"}
    
    try:
        shutil.rmtree(model_path)
        # Remove from cache
        key = str(model_path.resolve())
        if key in DashboardState.MODEL_CACHE:
            del DashboardState.MODEL_CACHE[key]
        if key in DashboardState.MODEL_CACHE_MTIME:
            del DashboardState.MODEL_CACHE_MTIME[key]
        return {"status": "deleted", "id": model_id}
    except Exception as e:
        return {"error": f"Failed to delete model checkpoint: {e}"}


@router.post("/api/benchmark")
def api_run_benchmark(
    request: Request,
    body: dict | None = None,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Run benchmark on current model."""
    _check_request_origin(request)
    _require_admin(_admin)
    body = body or {}
    model_id = str(body.get("model_id") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        return {"error": "Model path not allowed"}
    if not (model_path / "metadata.json").exists():
        return {"error": "No model to benchmark"}
    try:
        import subprocess
        meta = _read_metadata(model_path)
        data_path = body.get("data_path") or meta.get("train_data_path")
        if not data_path:
            latest_run = next((r for r in _read_run_history() if r.get("event") == "started"), {})
            data_name = latest_run.get("dataset")
            if data_name:
                data_path = next((str(p) for p in _dataset_index().values() if p.name == data_name), None)
        
        cmd = [
            sys.executable,
            str(_ROOT / "training" / "benchmark.py"),
            "--model",
            str(model_path),
            "--config",
            str(meta.get("train_config_name") or meta.get("config_name") or "seed"),
            "--max-samples",
            str(_clamp_int(body.get("max_samples"), 32, 1, 512)),
        ]
        if data_path:
            benchmark_data = Path(str(data_path))
            if benchmark_data.exists() and _is_within(benchmark_data, _dashboard_roots()):
                cmd.extend(["--data", str(benchmark_data)])
        
        logger.info("Running benchmark with command: %s", cmd)
        proc = subprocess.Popen(
            cmd,
            cwd=str(_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=45)
        if proc.returncode != 0:
            return {"error": f"Benchmark process failed: {stderr}"}
        
        bench_file = model_path / "benchmark.json"
        if bench_file.exists():
            return json.loads(bench_file.read_text(encoding="utf-8"))
        return {"status": "success", "stdout": stdout}
    except subprocess.TimeoutExpired:
        return {"error": "Benchmark timed out after 45 seconds"}
    except Exception as e:
        return {"error": str(e)}
