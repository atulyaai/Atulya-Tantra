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
        "meta": meta,
    }


@router.post("/api/plasticity/check")
def api_run_plasticity_check(
    request: Request,
    body: dict | None = None,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Run manual plasticity check on the model."""
    _check_request_origin(request)
    _require_admin(_admin)
    body = body or {}
    
    # 1. Check if training is running
    if DashboardState.TRAIN_PROC is not None and DashboardState.TRAIN_PROC.poll() is None:
        return {"error": "Training is currently active. Plasticity checks are managed automatically during training."}
        
    model_id = str(body.get("model_id") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        return {"error": "Model path not allowed"}
    if not (model_path / "metadata.json").exists():
        return {"error": "No model checkpoint to check plasticity on"}
        
    try:
        from atulya.dashboard.helpers import _load_cached_model
        from tantra.core.npdna.plasticity import PlasticityEngine
        import torch
        
        # Load core
        core = _load_cached_model(model_path)
        core.model.eval()
        
        # Reset usage counts
        for mesh in core.model.mesh_layers:
            mesh.reset_usage()
            
        # Try to find a few dataset texts for forwarding traffic through the router
        meta = _read_metadata(model_path)
        data_path = body.get("data_path") or meta.get("train_data_path")
        if not data_path:
            latest_run = next((r for r in _read_run_history() if r.get("event") == "started"), {})
            data_name = latest_run.get("dataset")
            if data_name:
                data_path = next((str(p) for p in _dataset_index().values() if p.name == data_name), None)
                
        texts = []
        if data_path and Path(data_path).exists():
            from tantra.training.dataset.build_dataset import load_dataset
            try:
                loaded = load_dataset(data_path, limit=10)
                texts = [x for x in loaded if x.strip()]
            except Exception:
                pass
                
        if not texts:
            # Fallback smoke texts if no dataset was found
            texts = [
                "The quick brown fox jumps over the lazy dog.",
                "Machine learning is a subset of artificial intelligence.",
                "Python is a versatile programming language used for web development.",
                "The Earth orbits the Sun at an average distance of 93 million miles.",
                "Gravity is the force that attracts objects toward each other.",
            ]
            
        device = next(core.model.parameters()).device
        with torch.no_grad():
            for text in texts:
                ids = core.encode(text, allow_growth=False)[:128]
                if len(ids) < 2:
                    continue
                input_ids = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
                core.model(input_ids)
                
        # Initialize PlasticityEngine and trigger check
        engine = PlasticityEngine(
            core,
            check_interval=1,
            dead_threshold=0.01,
            overload_threshold=0.18,
            grow_overloaded_strands=True,
            reinit_dead_strands=True,
        )
        
        events = engine.check(1)
        
        # If any events occurred, save model back to disk to commit changes (growth or reinitialization)
        if events:
            losses = meta.get("losses") or []
            core.save(model_path, losses=losses)
            
            # Read updated metadata
            meta = _read_metadata(model_path)
            
            # Invalidate the cached MODEL_CACHE_MTIME to force reload on next reference
            key = str(model_path.resolve())
            meta_path = model_path / "metadata.json"
            model_file = model_path / "model.pt"
            meta_mtime = meta_path.stat().st_mtime if meta_path.exists() else 0
            model_mtime = model_file.stat().st_mtime if model_file.exists() else 0
            mtime = max(meta_mtime, model_mtime)
            DashboardState.MODEL_CACHE_MTIME[key] = mtime
            
        # Get updated info
        bench_file = model_path / "benchmark.json"
        bench_data = None
        if bench_file.exists():
            try:
                bench_data = json.loads(bench_file.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        event_msgs = [f"[{e.event_type}] {e.details}" for e in events]
        summary_msg = f"Plasticity check completed. {len(events)} events: " + ", ".join(event_msgs) if events else "Plasticity check completed. No model adjustments needed."
        
        return {
            "status": "success",
            "message": summary_msg,
            "events": [
                {"step": e.step, "event_type": e.event_type, "details": e.details}
                for e in events
            ],
            "model_info": {
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
                "meta": meta,
            }
        }
    except Exception as e:
        logger.exception("Plasticity check failed")
        return {"error": f"Plasticity check failed: {e}"}



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
    proc = None
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
            "-m",
            "tantra.training.benchmark",
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
        stdout, stderr = proc.communicate(timeout=300)
        if proc.returncode != 0:
            return {"error": f"Benchmark process failed: {stderr}"}

        bench_file = model_path / "benchmark.json"
        if bench_file.exists():
            return json.loads(bench_file.read_text(encoding="utf-8"))
        return {"status": "success", "stdout": stdout}
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            proc.wait()
        return {"error": "Benchmark timed out after 300 seconds"}
    except Exception as e:
        return {"error": str(e)}
