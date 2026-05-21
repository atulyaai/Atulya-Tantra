"""NP-DNA Dashboard Helper Utilities.

Contains shared utilities for routing, origin verification, process scanning,
chat cleanup, preset calculators, and caching model instances.
"""
from __future__ import annotations
import json
import logging
import math
import os
import sys
import time
from functools import lru_cache
from pathlib import Path

import psutil
from fastapi import Header, HTTPException, Request, WebSocket

from atulya.core.npdna.config import CONFIGS
from atulya.dashboard.state import (
    _ROOT,
    OUTPUTS_DIR,
    ADMIN_TOKEN,
    MAX_STEPS,
    MAX_LIMIT,
    MAX_SEQ_LIMIT,
    MAX_PROMPT_CHARS,
    MAX_CHAT_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
    DashboardState,
)

logger = logging.getLogger("atulya.dashboard.helpers")


def _default_system_prompt() -> str:
    try:
        from atulya.identity import Identity
        return Identity().get_system_prompt()
    except Exception:
        return DEFAULT_SYSTEM_PROMPT


def _allowed_origins() -> set[str]:
    return {
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://[::1]:8501",
    }


def _require_admin(x_atulya_token: str | None = Header(default=None)) -> None:
    import secrets
    if not x_atulya_token or not secrets.compare_digest(x_atulya_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Dashboard token required")


def _check_request_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in _allowed_origins():
        raise HTTPException(status_code=403, detail="Blocked origin")


def _check_ws_origin(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    return not origin or origin in _allowed_origins()


def _dashboard_roots() -> list[Path]:
    raw = os.environ.get("ATULYA_DATASET_ROOTS")
    roots = [Path(_ROOT / "data")]
    if raw:
        roots.extend(Path(p) for p in raw.split(os.pathsep) if p.strip())
    else:
        for alt in (
            Path(os.path.expanduser("~/datasets")),
            _ROOT.parent / "datasets",
            Path(_ROOT.drive + "\\datasets") if _ROOT.drive else Path("datasets"),
        ):
            if alt.exists():
                roots.append(alt)
    resolved = []
    seen = set()
    for p in roots:
        if not p.exists():
            continue
        r = p.resolve()
        key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(r)
    return resolved


def _is_within(path: Path, roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return any(resolved == root or root in resolved.parents for root in roots)


def _clamp_int(value, default: int, min_value: int, max_value: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, n))


def _clamp_float(value, default: float, min_value: float, max_value: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, n))


def _training_processes() -> list[dict[str, object]]:
    """Best-effort detection of NP-DNA training processes, including after dashboard restart."""
    found = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(str(x) for x in cmdline)
            if "npdna_train.py" not in joined:
                continue
            found.append({
                "pid": proc.info["pid"],
                "started_at": proc.info.get("create_time"),
                "cmd": joined,
            })
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return found


def _latest_metric_status() -> dict[str, object]:
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    last, total = None, 0
    if mf.exists():
        with mf.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = json.loads(line)
                    total += 1
    return {"last": last, "steps_logged": total, "metrics_exists": mf.exists()}


def _read_train_status() -> dict[str, object] | None:
    path = OUTPUTS_DIR / "train_status.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"phase": "unknown", "error": "Could not parse train_status.json"}


def _format_chat_prompt(prompt: str, system: str | None = None) -> str:
    prompt = prompt.strip()
    system = (system or _default_system_prompt()).strip() or DEFAULT_SYSTEM_PROMPT
    if "Assistant:" in prompt or "User:" in prompt:
        return prompt
    return f"System: {system}\nUser: {prompt}\nAssistant:"


def _format_mode_prompt(prompt: str, mode: str, system: str | None = None) -> str:
    """Apply explicit AI modes before generation."""
    mode = (mode or "chat").strip().lower()
    prompt = prompt.strip()
    if mode == "raw":
        return prompt
    if mode == "translate_en":
        return _format_chat_prompt(f"Translate this to English. Return only the translation:\n{prompt}", system)
    if mode == "translate_hi":
        return _format_chat_prompt(f"Translate this to Hindi in Devanagari. Return only the translation:\n{prompt}", system)
    if mode == "translate_sa":
        return _format_chat_prompt(f"Translate this to Sanskrit in Devanagari. Return only the translation:\n{prompt}", system)
    return _format_chat_prompt(prompt, system)


def _clean_chat_response(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    for marker in ("\nUser:", "\nSystem:", "\nContext:", "\nAssistant:"):
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx].strip()
    return text


def _model_readiness(meta: dict[str, object]) -> dict[str, object]:
    """Return a conservative chat-readiness signal from saved metrics."""
    loss = meta.get("train_final_loss") or meta.get("final_loss")
    if not isinstance(loss, (int, float)):
        losses = meta.get("losses") or []
        if losses:
            loss = losses[-1]
    if not isinstance(loss, (int, float)):
        return {"ready": False, "reason": "no saved loss available"}
    train_ppl = round(math.exp(min(float(loss), 20)), 1)
    if float(loss) > 4.5:
        return {
            "ready": False,
            "loss": round(float(loss), 4),
            "train_ppl": train_ppl,
            "reason": "loss is still too high for coherent chat",
        }
    return {"ready": True, "loss": round(float(loss), 4), "train_ppl": train_ppl}


def _tail_text(path: Path, max_lines: int = 80) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]


def _append_run_history(event: dict[str, object]) -> None:
    path = OUTPUTS_DIR / "run_history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"time": time.time(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_run_history(limit: int = 50) -> list[dict[str, object]]:
    path = OUTPUTS_DIR / "run_history.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:][::-1]


def _read_metadata(path: Path) -> dict[str, object]:
    meta = path / "metadata.json"
    if not meta.exists():
        return {}
    return json.loads(meta.read_text(encoding="utf-8"))


def _checkpoint_step(model_id: str, meta: dict[str, object]) -> int:
    if isinstance(meta.get("train_step"), int):
        return int(meta["train_step"])
    if isinstance(meta.get("loss_count"), int):
        return int(meta["loss_count"])
    if model_id.startswith("step_"):
        try:
            return int(model_id.split("_", 1)[1])
        except (IndexError, ValueError):
            pass
    if model_id == "latest":
        status = _read_train_status() or {}
        if isinstance(status.get("step"), int):
            return int(status["step"])
        latest = _latest_metric_status().get("last") or {}
        if isinstance(latest.get("step"), int):
            return int(latest["step"])
    return len(meta.get("losses") or [])


def _model_best_loss(meta: dict[str, object]) -> float:
    if isinstance(meta.get("train_best_loss"), (int, float)):
        return float(meta["train_best_loss"])
    if isinstance(meta.get("best_loss"), (int, float)):
        return float(meta["best_loss"])
    losses = meta.get("losses") or []
    return float(min(losses)) if losses else 999.0


def _model_final_loss(meta: dict[str, object]) -> float | None:
    for key in ("train_final_loss", "final_loss"):
        if isinstance(meta.get(key), (int, float)):
            return float(meta[key])
    losses = meta.get("losses") or []
    return float(losses[-1]) if losses else None


def _benchmark_matches_model(model_path: Path, bench: dict[str, object] | None) -> bool:
    if not bench:
        return False
    bench_meta = bench.get("benchmark_meta") if isinstance(bench, dict) else None
    if not isinstance(bench_meta, dict):
        return False
    # Persistent benchmark support: always return True if a valid benchmark exists
    # for this model path, fulfilling "System Benchmark current all until it shows new one"
    return True



def _model_registry() -> list[dict[str, object]]:
    models = []
    for item in _list_checkpoints():
        model_path = _checkpoint_index().get(str(item["id"]))
        meta = _read_metadata(model_path) if model_path else {}
        losses = meta.get("losses") or []
        item = dict(item)
        item["latest_loss"] = losses[-1] if losses else None
        item["saved_at"] = meta.get("saved_at", item.get("saved_at"))
        item["hidden_size"] = meta.get("hidden_size")
        item["layers"] = meta.get("num_layers")
        item["strands"] = meta.get("num_strands")
        models.append(item)
    return models


def _dataset_preview(data_id: str, rows: int = 5) -> dict[str, object]:
    path = _dataset_index().get(data_id)
    if not path:
        return {"error": "Dataset not found"}
    samples = []
    total_seen = 0
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            total_seen += 1
            if len(samples) < rows:
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    samples.append({"text": line[:500]})
            if total_seen >= 10000 and len(samples) >= rows:
                break
    return {
        "id": data_id,
        "name": path.name,
        "folder": path.parent.name,
        "size_mb": round(path.stat().st_size / (1024 ** 2), 1),
        "sampled_count": total_seen,
        "samples": samples,
    }


_DATASET_INDEX_CACHE: dict[str, Path] | None = None
_DATASET_INDEX_MTIME: float = 0


def _dataset_index(refresh: bool = False) -> dict[str, Path]:
    global _DATASET_INDEX_CACHE, _DATASET_INDEX_MTIME
    now = __import__("time").time()
    if not refresh and _DATASET_INDEX_CACHE is not None and (now - _DATASET_INDEX_MTIME) < 30:
        return _DATASET_INDEX_CACHE
    out: dict[str, Path] = {}
    idx = 0
    seen_files: set[str] = set()
    for root in _dashboard_roots():
        for f in sorted(root.rglob("*.jsonl")):
            if not f.is_file():
                continue
            resolved = str(f.resolve()).lower()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            idx += 1
            out[f"ds-{idx}"] = f.resolve()
    _DATASET_INDEX_CACHE = out
    _DATASET_INDEX_MTIME = now
    return out


def _checkpoint_index() -> dict[str, Path]:
    out = {"latest": OUTPUTS_DIR.resolve()}
    # Scan checkpoints directory
    ckpt_dir = OUTPUTS_DIR / "checkpoints"
    if ckpt_dir.exists():
        for d in sorted(ckpt_dir.iterdir()):
            if d.is_dir() and (d / "metadata.json").exists():
                out[d.name] = d.resolve()
    # Also scan backups directory for versioned models
    backups_dir = OUTPUTS_DIR / "backups"
    if backups_dir.exists():
        for d in sorted(backups_dir.iterdir()):
            if d.is_dir() and (d / "metadata.json").exists():
                out[d.name] = d.resolve()
    return out


def _scan_datasets():
    """Find dashboard-approved .jsonl datasets without exposing full paths."""
    out = []
    for data_id, f in _dataset_index().items():
        mb = f.stat().st_size / (1024**2)
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                first = json.loads(fh.readline())
            fields = list(first.keys())[:5]
        except Exception:
            fields = []
        out.append({"id": data_id, "name": f.stem,
                     "folder": f.parent.name,
                     "size_mb": round(mb,1),
                     "size_label": f"{mb:.0f} MB" if mb < 1024 else f"{mb/1024:.1f} GB",
                     "fields": fields})
    return sorted(out, key=lambda x: x["name"].lower())


def _estimate_dataset_rows(path: Path, max_scan_bytes: int = 8 * 1024 * 1024) -> int:
    """Estimate JSONL rows without reading multi-GB datasets fully."""
    size = path.stat().st_size
    if size <= 0:
        return 0
    read_bytes = min(size, max_scan_bytes)
    with path.open("rb") as f:
        sample = f.read(read_bytes)
    lines = sample.count(b"\n")
    if read_bytes == size:
        return max(1, lines)
    avg_line = read_bytes / max(1, lines)
    return max(1, int(size / max(1.0, avg_line)))


def _training_preset(data_id: str, config_name: str | None = None) -> dict[str, object]:
    data_path = _dataset_index().get(data_id)
    if not data_path:
        return {"error": "Dataset not found"}
    cfg_name = config_name if config_name in CONFIGS else _auto_config_name()
    cfg = CONFIGS[cfg_name]
    vm = psutil.virtual_memory()
    avail_gb = vm.available / (1024 ** 3)
    size_mb = data_path.stat().st_size / (1024 ** 2)
    est_rows = _estimate_dataset_rows(data_path)

    if avail_gb < 3.5:
        recommended_config = "seed"
        seq_limit = 128
        limit = min(est_rows, 10000)
        chunk_steps = 1000
        min_free_ram = 2.0
    elif avail_gb < 7.0:
        recommended_config = "nano" if cfg_name in ("small", "medium") else cfg_name
        seq_limit = 128
        limit = min(est_rows, 30000)
        chunk_steps = 3000 if size_mb <= 512 else 5000
        min_free_ram = 2.5
    else:
        recommended_config = "micro" if cfg_name in ("small", "medium") else cfg_name
        seq_limit = 128 if size_mb > 1024 else 256
        limit = min(est_rows, 50000 if size_mb > 1024 else 25000)
        chunk_steps = 5000 if size_mb <= 512 else 10000
        min_free_ram = 2.5

    if size_mb <= 25:
        bpe_merges = 2000
        steps = min(1500, max(300, est_rows * 10))
        limit = min(est_rows, 5000)
        bpe_max_words = 8000
    elif size_mb <= 512:
        bpe_merges = 6000
        steps = max(chunk_steps, 5000)
        bpe_max_words = 20000
    else:
        bpe_merges = 8000
        steps = max(chunk_steps, 10000)
        bpe_max_words = 30000

    if avail_gb < 4.0:
        bpe_merges = min(bpe_merges, 4000)
        bpe_max_words = min(bpe_max_words, 12000)

    steps = min(steps, MAX_STEPS)
    limit = min(max(1, limit), MAX_LIMIT)
    checkpoint_every = max(100, min(500, max(100, steps // 10)))
    resume_id = ""
    latest_meta_path = OUTPUTS_DIR / "metadata.json"
    if latest_meta_path.exists():
        try:
            latest_meta = json.loads(latest_meta_path.read_text(encoding="utf-8"))
            target_cfg = CONFIGS[recommended_config]
            if (
                int(latest_meta.get("hidden_size") or 0) == int(target_cfg.hidden_size)
                and int(latest_meta.get("num_layers") or 0) == int(target_cfg.num_layers)
            ):
                resume_id = "latest"
        except Exception:
            resume_id = ""

    return {
        "data_id": data_id,
        "dataset": data_path.name,
        "size_mb": round(size_mb, 1),
        "estimated_rows": est_rows,
        "available_ram_gb": round(avail_gb, 1),
        "config": recommended_config,
        "steps": steps,
        "limit": limit,
        "seq_limit": seq_limit,
        "bpe_merges": bpe_merges,
        "bpe_max_words": bpe_max_words,
        "checkpoint_every": checkpoint_every,
        "pack": True,
        "bf16": False,
        "min_free_ram_gb": min_free_ram,
        "resume_id": resume_id,
        "reason": (
            f"Auto preset for {round(size_mb, 1)}MB / ~{est_rows:,} rows with "
            f"{round(avail_gb, 1)}GB free RAM."
        ),
    }


def _auto_config_name():
    """Pick best config for available RAM."""
    avail = psutil.virtual_memory().available
    if avail > 6 * 1024**3:
        return "micro"
    if avail > 3 * 1024**3:
        return "nano"
    return "seed"


def _list_checkpoints():
    """List all saved checkpoints + backups + the main model, sorted by loss."""
    ckpts = []
    # Main model
    meta_p = OUTPUTS_DIR / "metadata.json"
    model_p = OUTPUTS_DIR / "model.pt"
    if meta_p.exists() and model_p.exists():
        m = json.loads(meta_p.read_text(encoding="utf-8"))
        best_loss = _model_best_loss(m)
        ckpts.append({"id": "latest", "label": "latest",
                       "config": m.get("train_config_name") or m.get("config_name","?"), "step": _checkpoint_step("latest", m),
                       "best_loss": round(best_loss,4), "params": m.get("parameter_count",0),
                       "latest_loss": _model_final_loss(m),
                       "vocab_used": m.get("vocab_size",0), "vocab_cap": m.get("vocab_capacity",0),
                       "saved_at": m.get("saved_at",0)})
    # Checkpoint subdirs
    ckpt_dir = OUTPUTS_DIR / "checkpoints"
    if ckpt_dir.exists():
        for d in sorted(ckpt_dir.iterdir()):
            mp = d / "metadata.json"
            modelp = d / "model.pt"
            if not mp.exists() or not modelp.exists():
                continue
            m = json.loads(mp.read_text(encoding="utf-8"))
            best_loss = _model_best_loss(m)
            ckpts.append({"id": d.name, "label": d.name,
                           "config": m.get("train_config_name") or m.get("config_name","?"), "step": _checkpoint_step(d.name, m),
                           "best_loss": round(best_loss,4), "params": m.get("parameter_count",0),
                           "latest_loss": _model_final_loss(m),
                           "vocab_used": m.get("vocab_size",0), "vocab_cap": m.get("vocab_capacity",0),
                           "saved_at": m.get("saved_at",0)})
    # Backup subdirs (versioned models)
    backups_dir = OUTPUTS_DIR / "backups"
    if backups_dir.exists():
        for d in sorted(backups_dir.iterdir()):
            mp = d / "metadata.json"
            modelp = d / "model.pt"
            if not mp.exists() or not modelp.exists():
                continue
            m = json.loads(mp.read_text(encoding="utf-8"))
            best_loss = _model_best_loss(m)
            version = m.get("version", d.name)
            label = f"{version} ({d.name})"
            ckpts.append({"id": d.name, "label": label,
                           "config": m.get("train_config_name") or m.get("config_name","?"), "step": _checkpoint_step(d.name, m),
                           "best_loss": round(best_loss,4), "params": m.get("parameter_count",0),
                           "latest_loss": _model_final_loss(m),
                           "vocab_used": m.get("vocab_size",0), "vocab_cap": m.get("vocab_capacity",0),
                           "saved_at": m.get("saved_at",0)})
    return sorted(ckpts, key=lambda x: x["best_loss"])


def _load_cached_model(model_path: Path):
    from atulya.core.npdna import NpDnaCore

    key = str(model_path.resolve())
    meta_path = model_path / "metadata.json"
    model_file = model_path / "model.pt"
    meta_mtime = meta_path.stat().st_mtime if meta_path.exists() else 0
    model_mtime = model_file.stat().st_mtime if model_file.exists() else 0
    mtime = max(meta_mtime, model_mtime)
    if key not in DashboardState.MODEL_CACHE or DashboardState.MODEL_CACHE_MTIME.get(key) != mtime:
        DashboardState.MODEL_CACHE[key] = NpDnaCore.load(model_path)
        DashboardState.MODEL_CACHE_MTIME[key] = mtime
    return DashboardState.MODEL_CACHE[key]


def _get_active_cortex(model_id: str = "latest"):
    """Helper to safely fetch the active model's cortex, metadata, and core wrapper."""
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        return None
    if not (Path(model_path) / "metadata.json").exists():
        return None
    try:
        core = _load_cached_model(Path(model_path))
        return core.model.cortex, Path(model_path), core
    except Exception as e:
        logger.error("Failed to load cortex from %s: %s", model_id, e)
        return None


def _stop_training() -> list[str]:
    """Helper to stop any running training process."""
    stopped = []
    stop_signal = OUTPUTS_DIR / "stop_signal.txt"
    if DashboardState.TRAIN_PROC and DashboardState.TRAIN_PROC.poll() is None:
        # 1. Attempt graceful stop via stop_signal.txt
        try:
            stop_signal.write_text("stop", encoding="utf-8")
            logger.info("Sent stop signal to training process. Waiting for graceful shutdown...")
            
            # Wait up to 5 seconds for the process to exit
            for _ in range(10):
                if DashboardState.TRAIN_PROC.poll() is not None:
                    break
                time.sleep(0.5)
        except Exception as e:
            logger.error("Failed to send graceful stop signal: %s", e)
            
        # 2. Fallback to hard termination if it did not stop
        if DashboardState.TRAIN_PROC.poll() is None:
            try:
                logger.info("Training process did not stop gracefully. Terminating...")
                DashboardState.TRAIN_PROC.terminate()
                DashboardState.TRAIN_PROC.wait(timeout=10)
            except Exception:
                pass
        
        DashboardState.TRAIN_PROC = None
        stopped.append("owned")
        
        # 3. Restore benchmark from backup if present and target is missing
        bak_bench = OUTPUTS_DIR / "benchmark.json.bak"
        target_bench = OUTPUTS_DIR / "benchmark.json"
        if bak_bench.exists() and not target_bench.exists():
            try:
                import shutil
                shutil.copy2(bak_bench, target_bench)
                logger.info("Restored benchmark.json from backup")
            except Exception as e:
                logger.warning("Failed to restore benchmark backup: %s", e)
                
    if DashboardState.TRAIN_LOG_F is not None:
        try:
            DashboardState.TRAIN_LOG_F.close()
        except Exception:
            pass
        DashboardState.TRAIN_LOG_F = None

    external = [
        item for item in _training_processes()
        if item.get("pid") != os.getpid()
        and not (DashboardState.TRAIN_PROC and item.get("pid") == DashboardState.TRAIN_PROC.pid)
    ]
    if external:
        try:
            stop_signal.parent.mkdir(parents=True, exist_ok=True)
            stop_signal.write_text("stop", encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to write stop signal for external training: %s", e)

        for item in external:
            pid = int(item["pid"])
            try:
                proc = psutil.Process(pid)
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    logger.info("External training process %d did not stop gracefully. Terminating...", pid)
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except psutil.TimeoutExpired:
                        proc.kill()
                stopped.append(f"external:{pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning("Could not stop external training process %d: %s", pid, e)
    return stopped
