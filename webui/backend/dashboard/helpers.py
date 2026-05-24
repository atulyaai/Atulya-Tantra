"""Dashboard helper functions."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

from fastapi import Header, HTTPException

from .state import ADMIN_TOKEN, DATASETS_DIR, DashboardState, OUTPUTS_DIR

logger = logging.getLogger(__name__)


def _require_admin(token: str | None = Header(default=None, alias="X-Atulya-Token")) -> None:
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _check_request_origin() -> None:
    return None


def _checkpoint_index() -> dict[str, Path]:
    index = {}
    versions = OUTPUTS_DIR / "versions"
    newest: Path | None = None
    if versions.exists():
        items = [item for item in versions.iterdir() if item.is_dir() and (item / "metadata.json").exists()]
        items.sort(key=lambda p: (p / "metadata.json").stat().st_mtime, reverse=True)
        newest = items[0] if items else None
        for item in items:
            index[item.name] = item
    if (OUTPUTS_DIR / "metadata.json").exists():
        newest = newest or OUTPUTS_DIR
        index[OUTPUTS_DIR.name] = OUTPUTS_DIR
    if newest is not None:
        index["latest"] = newest
    return index


def _read_metadata(path: str | Path) -> dict:
    meta = Path(path) / "metadata.json"
    if not meta.exists():
        return {}
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _checkpoint_step(name: str, meta: dict) -> int:
    return int(meta.get("train_step") or meta.get("loss_count") or 0)


def _model_best_loss(meta: dict) -> float:
    losses = meta.get("losses") or []
    values = [x for x in [meta.get("best_loss"), meta.get("train_best_loss"), min(losses) if losses else None] if x is not None]
    return float(min(values)) if values else 999.0


def _model_final_loss(meta: dict) -> float | None:
    return meta.get("final_loss") or meta.get("train_final_loss")


def _model_registry() -> list[dict]:
    models = []
    for model_id, path in _checkpoint_index().items():
        meta = _read_metadata(path)
        models.append({
            "id": model_id,
            "label": model_id,
            "config": meta.get("train_config_name") or meta.get("config_name", "?"),
            "step": _checkpoint_step(model_id, meta),
            "best_loss": _model_best_loss(meta),
            "saved_at": meta.get("saved_at", 0),
        })
    return models


_MODEL_CACHE_LOCK = threading.Lock()

def _load_cached_model(model_path: Path):
    from tantra.npdna import NpDnaCore

    key = str(model_path.resolve())
    meta = model_path / "metadata.json"
    mtime = meta.stat().st_mtime if meta.exists() else 0
    with _MODEL_CACHE_LOCK:
        if key not in DashboardState.MODEL_CACHE or DashboardState.MODEL_CACHE_MTIME.get(key) != mtime:
            DashboardState.MODEL_CACHE[key] = NpDnaCore.load(model_path)
            DashboardState.MODEL_CACHE_MTIME[key] = mtime
    return DashboardState.MODEL_CACHE[key]


def _dataset_index() -> dict[str, Path]:
    if not DATASETS_DIR.exists():
        return {}
    files = []
    for pattern in ("*.jsonl", "*.json"):
        files.extend(DATASETS_DIR.glob(pattern))
    return {p.name: p for p in sorted(files)}


def _file_size_label(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def _dataset_records(path: Path, limit: int = 3) -> tuple[int | None, list[Any]]:
    samples: list[Any] = []
    count = 0
    try:
        if path.suffix.lower() == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                count += 1
                if len(samples) < limit:
                    try:
                        samples.append(json.loads(line))
                    except Exception:
                        samples.append(line[:300])
            return count, samples
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data), data[:limit]
        if isinstance(data, dict):
            records = data.get("samples") or data.get("data") or data.get("conversations")
            if isinstance(records, list):
                return len(records), records[:limit]
            return None, [data]
    except Exception:
        return None, []
    return None, []


def _dataset_registry() -> list[dict]:
    datasets = []
    for dataset_id, path in _dataset_index().items():
        count, samples = _dataset_records(path, limit=1)
        datasets.append({
            "id": dataset_id,
            "name": path.stem,
            "path": str(path),
            "size": path.stat().st_size,
            "size_label": _file_size_label(path.stat().st_size),
            "rows": count,
            "sample": samples[0] if samples else None,
        })
    return datasets


def _tail_lines(path: Path, max_lines: int = 80) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except Exception as exc:
        logger.debug("Failed to tail %s: %s", path, exc)
        return []


def _pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except Exception as exc:
        logger.debug("psutil pid check failed: %s", exc)
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def _python_executable() -> str:
    return os.environ.get("ATULYA_TRAIN_PYTHON") or sys.executable


def _latest_status_path() -> Path | None:
    candidates = []
    if (OUTPUTS_DIR / "train_status.json").exists():
        candidates.append(OUTPUTS_DIR / "train_status.json")
    versions = OUTPUTS_DIR / "versions"
    if versions.exists():
        candidates.extend(versions.glob("*/train_status.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _latest_metrics_path() -> Path | None:
    candidates = []
    if (OUTPUTS_DIR / "live_metrics.jsonl").exists():
        candidates.append(OUTPUTS_DIR / "live_metrics.jsonl")
    versions = OUTPUTS_DIR / "versions"
    if versions.exists():
        candidates.extend(versions.glob("*/live_metrics.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_status_file() -> dict:
    path = _latest_status_path()
    if not path:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = str(path)
        return data
    except Exception as exc:
        logger.debug("Failed to read status file %s: %s", path, exc)
        return {"_path": str(path), "phase": "unreadable"}


def _run_history() -> list[dict]:
    runs = []
    for model_id, path in _checkpoint_index().items():
        if model_id == "latest":
            continue
        meta = _read_metadata(path)
        runs.append({
            "event": meta.get("version_stage") or "checkpoint_saved",
            "config": meta.get("train_config_name") or meta.get("config_name", "?"),
            "steps": meta.get("train_step") or meta.get("loss_count") or 0,
            "best_loss": _model_best_loss(meta),
            "final_loss": _model_final_loss(meta),
            "time": meta.get("saved_at") or path.stat().st_mtime,
            "model_id": model_id,
        })
    return sorted(runs, key=lambda item: item["time"], reverse=True)


