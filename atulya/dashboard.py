"""NP-DNA Command Center — Production Admin Panel.

All-in-one: train, chat, monitor, manage checkpoints.
Runs training as subprocess, streams metrics via WebSocket.

Usage:  python atulya/dashboard.py
        Open http://localhost:8501
"""
from __future__ import annotations
import asyncio, json, logging, math, os, platform, secrets, subprocess, sys, time
from functools import lru_cache
from pathlib import Path

import psutil
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from atulya.core.npdna.config import CONFIGS, _estimate_params

logger = logging.getLogger(__name__)
app = FastAPI(title="NP-DNA Command Center")

OUTPUTS_DIR = _ROOT / "outputs" / "npdna"
TRAIN_PROC: subprocess.Popen | None = None
_MODEL_CACHE: dict[str, object] = {}
_MODEL_CACHE_MTIME: dict[str, float] = {}

MAX_STEPS = int(os.environ.get("ATULYA_DASHBOARD_MAX_STEPS", "10000"))
MAX_LIMIT = int(os.environ.get("ATULYA_DASHBOARD_MAX_LIMIT", "50000"))
MAX_SEQ_LIMIT = int(os.environ.get("ATULYA_DASHBOARD_MAX_SEQ_LIMIT", "512"))
MAX_PROMPT_CHARS = int(os.environ.get("ATULYA_DASHBOARD_MAX_PROMPT_CHARS", "4000"))
MAX_CHAT_TOKENS = int(os.environ.get("ATULYA_DASHBOARD_MAX_TOKENS", "256"))
MAX_HISTORY_POINTS = int(os.environ.get("ATULYA_DASHBOARD_HISTORY", "300"))
DEFAULT_SYSTEM_PROMPT = "You are Atulya. Be warm, thoughtful, and direct."


def _load_admin_token() -> tuple[str, str]:
    env_token = os.environ.get("ATULYA_DASHBOARD_TOKEN", "").strip()
    if env_token:
        return env_token, "env"
    token_path = OUTPUTS_DIR / "dashboard_token.txt"
    token = secrets.token_urlsafe(24)
    try:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # Open with owner-only permissions (0o600)
        fd = os.open(str(token_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(token + "\n")
        except Exception:
            os.close(fd)
            raise
        # Apply chmod fallback just in case
        try:
            os.chmod(str(token_path), 0o600)
        except OSError:
            pass
        return token, str(token_path)
    except OSError:
        return token, "session"


ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = _load_admin_token()


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
    if x_atulya_token != ADMIN_TOKEN:
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
    model_file = model_path / "model.pt"
    meta_file = model_path / "metadata.json"
    try:
        return (
            abs(float(bench_meta.get("model_mtime")) - model_file.stat().st_mtime) < 0.001
            and abs(float(bench_meta.get("metadata_mtime")) - meta_file.stat().st_mtime) < 0.001
        )
    except (TypeError, ValueError, OSError):
        return False


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


@lru_cache(maxsize=1)
def _dataset_index() -> dict[str, Path]:
    out: dict[str, Path] = {}
    idx = 0
    for root in _dashboard_roots():
        for f in sorted(root.rglob("*.jsonl")):
            if not f.is_file():
                continue
            idx += 1
            out[f"ds-{idx}"] = f.resolve()
    return out


def _checkpoint_index() -> dict[str, Path]:
    out = {"latest": OUTPUTS_DIR.resolve()}
    ckpt_dir = OUTPUTS_DIR / "checkpoints"
    if ckpt_dir.exists():
        for d in sorted(ckpt_dir.iterdir()):
            if d.is_dir() and (d / "metadata.json").exists():
                out[d.name] = d.resolve()
    return out

# ── helpers ──────────────────────────────────────────────────────────────

def _scan_datasets():
    """Find dashboard-approved .jsonl datasets without exposing full paths."""
    out = []
    for data_id, f in _dataset_index().items():
        mb = f.stat().st_size / (1024**2)
        try:
            first = json.loads(f.open(encoding="utf-8", errors="ignore").readline())
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
    elif size_mb <= 512:
        bpe_merges = 8000
        steps = max(chunk_steps, 5000)
    else:
        bpe_merges = 16000
        steps = max(chunk_steps, 10000)

    if avail_gb < 4.0:
        bpe_merges = min(bpe_merges, 4000)
    bpe_max_words = 0

    steps = min(steps, MAX_STEPS)
    limit = min(max(1, limit), MAX_LIMIT)
    checkpoint_every = max(100, min(500, max(100, steps // 10)))

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
        "resume_id": "latest" if (OUTPUTS_DIR / "metadata.json").exists() else "",
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
    """List all saved checkpoints + the main model, sorted by loss."""
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
    return sorted(ckpts, key=lambda x: x["best_loss"])

# ── API ──────────────────────────────────────────────────────────────────

@app.post("/api/auth/verify")
def api_auth_verify(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    return {"status": "ok"}

@app.get("/api/datasets")
def api_datasets(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    _dataset_index.cache_clear()
    return {"datasets": _scan_datasets()}

@app.get("/api/configs")
def api_configs(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    auto = _auto_config_name()
    out = []
    for name, cfg in CONFIGS.items():
        est = _estimate_params(cfg)
        out.append({"name": name, "hidden": cfg.hidden_size, "state": cfg.state_size,
                     "layers": cfg.num_layers, "strands": cfg.mesh.num_strands,
                     "top_k": cfg.mesh.top_k, "vocab": cfg.initial_vocab,
                     "params": est, "params_label": f"{est/1e6:.1f}M" if est>1e6 else f"{est/1e3:.0f}K",
                     "mem_mb": round(est*4/(1024**2),1), "recommended": name == auto})
    return {"configs": out, "auto": auto}

@app.get("/api/system")
def api_system(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    vm = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    gpu = "unavailable"
    try:
        import torch

        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
    except Exception:
        gpu = "unknown"
    return {"ram_total_gb": round(vm.total/1e9,1), "ram_avail_gb": round(vm.available/1e9,1),
            "ram_pct": vm.percent, "cpu_pct": cpu, "cpu_count": psutil.cpu_count(),
            "platform": platform.platform(), "python": platform.python_version(), "gpu": gpu}

@app.get("/api/model")
def api_model(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    meta_p = OUTPUTS_DIR / "metadata.json"
    if not meta_p.exists():
        return {"exists": False}
    m = json.loads(meta_p.read_text(encoding="utf-8"))
    bench_p = OUTPUTS_DIR / "benchmark.json"
    bench = json.loads(bench_p.read_text(encoding="utf-8")) if bench_p.exists() else None
    if bench and not _benchmark_matches_model(OUTPUTS_DIR, bench):
        bench = None
    return {"exists": True, "meta": m, "benchmark": bench}

@app.get("/api/checkpoints")
def api_checkpoints(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"checkpoints": _list_checkpoints()}


@app.get("/api/models")
def api_models(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"models": _model_registry()}

@app.delete("/api/models/{model_id}")
def api_delete_model(
    model_id: str,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    import shutil
    
    if model_id == "latest":
        return {"error": "Cannot manually delete 'latest' model individually. Use Factory Reset."}

    ckpt_dir = _checkpoint_index().get(model_id)
    checkpoint_root = (OUTPUTS_DIR / "checkpoints").resolve()
    if (
        not ckpt_dir
        or not ckpt_dir.exists()
        or not ckpt_dir.is_dir()
        or checkpoint_root not in ckpt_dir.parents
    ):
        return {"error": f"Checkpoint {model_id} not found."}
        
    try:
        shutil.rmtree(ckpt_dir)
        _MODEL_CACHE.clear()
        _MODEL_CACHE_MTIME.clear()
        return {"status": "deleted", "id": model_id}
    except Exception as e:
        return {"error": f"Failed to delete: {str(e)}"}


@app.get("/api/run-history")
def api_run_history(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"runs": _read_run_history()}


@app.get("/api/dataset-preview/{data_id}")
def api_dataset_preview(
    data_id: str,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    return _dataset_preview(data_id)


@app.get("/api/train/preset/{data_id}")
def api_train_preset(
    data_id: str,
    config: str | None = None,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    return _training_preset(data_id, config)

@app.get("/api/training-status")
def api_train_status(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    global TRAIN_PROC
    owned_running = TRAIN_PROC is not None and TRAIN_PROC.poll() is None
    external = _training_processes()
    status = _latest_metric_status()
    return {
        "running": owned_running or bool(external),
        "owned": owned_running,
        "external": external,
        "status": _read_train_status(),
        "log_tail": _tail_text(OUTPUTS_DIR / "train.log", 80),
        **status,
    }


@app.get("/api/train-log")
def api_train_log(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {
        "status": _read_train_status(),
        "log_tail": _tail_text(OUTPUTS_DIR / "train.log", 120),
    }

@app.post("/api/train/start")
def api_train_start(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    global TRAIN_PROC
    if TRAIN_PROC and TRAIN_PROC.poll() is None:
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
    checkpoint_every = _clamp_int(body.get("checkpoint_every"), 100, 0, max(1000, MAX_STEPS))
    lr = _clamp_float(body.get("lr"), 5e-4, 1e-6, 1.0)
    seq_limit = _clamp_int(body.get("seq_limit"), 256, 32, MAX_SEQ_LIMIT)
    # Clear old live metrics
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    mf.parent.mkdir(parents=True, exist_ok=True)
    if mf.exists(): mf.unlink()
    bench_file = OUTPUTS_DIR / "benchmark.json"
    if bench_file.exists(): bench_file.unlink()
    status_file = OUTPUTS_DIR / "train_status.json"
    if status_file.exists(): status_file.unlink()
    cmd = [sys.executable, str(_ROOT/"training"/"npdna_train.py"),
           "--config", config, "--steps", str(steps),
           "--lr", str(lr), "--data", str(data_path),
           "--limit", str(limit), "--log-every", "5",
           "--seq-limit", str(seq_limit),
           "--checkpoint-every", str(checkpoint_every),
           "--device", "auto",
           "--bpe-merges", str(_clamp_int(body.get("bpe_merges"), 2000, 0, 16000)),
           "--bpe-max-words", str(_clamp_int(body.get("bpe_max_words"), 0, 0, 50000)),
           "--min-free-ram-gb", str(_clamp_float(body.get("min_free_ram_gb"), 1.5, 0.5, 16.0)),
           "--balance-weight", str(_clamp_float(body.get("balance_weight"), 0.05, 0.0, 1.0)),
           "--plasticity-interval", str(_clamp_int(body.get("plasticity_interval"), max(10, steps // 40), 10, max(10, steps))),
           "--plasticity-overload-threshold", str(_clamp_float(body.get("plasticity_overload_threshold"), 0.14, 0.05, 0.8)),
           "--plasticity-dead-threshold", str(_clamp_float(body.get("plasticity_dead_threshold"), 0.01, 0.0, 0.2)),
           "--plasticity-grow-cooldown", str(_clamp_int(body.get("plasticity_grow_cooldown"), 1, 0, 20)),
           "--lr-schedule", "cosine"]
    if body.get("bf16", False): cmd.append("--bf16")
    if body.get("pack", True): cmd.append("--pack")
    resume_id = body.get("resume_id")
    if resume_id is None:
        resume_id = body.get("resume_from")
    if resume_id is None and (OUTPUTS_DIR / "metadata.json").exists():
        resume_id = "latest"
    if resume_id:
        resume = _checkpoint_index().get(str(resume_id))
        if not resume:
            return {"error": "Resume checkpoint not found or not allowed"}
        cmd.extend(["--resume", str(resume)])
    log_path = OUTPUTS_DIR / "train.log"
    log_f = log_path.open("a", encoding="utf-8")
    TRAIN_PROC = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=log_f,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
    _append_run_history({
        "event": "started",
        "pid": TRAIN_PROC.pid,
        "config": config,
        "steps": steps,
        "limit": limit,
        "seq_limit": seq_limit,
        "dataset": data_path.name,
        "resume": str(resume_id) if resume_id else "fresh",
    })
    return {"status":"started", "pid": TRAIN_PROC.pid}

@app.post("/api/train/stop")
def api_train_stop(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    global TRAIN_PROC
    stopped = []
    if TRAIN_PROC and TRAIN_PROC.poll() is None:
        TRAIN_PROC.terminate(); TRAIN_PROC.wait(timeout=10); TRAIN_PROC = None
        stopped.append("owned")
    if stopped:
        return {"status":"stopped", "stopped": stopped}
    return {"status":"not_running"}

@app.post("/api/system/reset")
def api_system_reset(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Factory reset: delete all model outputs but keep datasets."""
    _check_request_origin(request)
    _require_admin(_admin)
    import shutil
    
    # 1. Stop any running training
    api_train_stop(request, _admin)
    
    # 2. Delete everything inside OUTPUTS_DIR
    deleted = []
    if OUTPUTS_DIR.exists():
        for item in OUTPUTS_DIR.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    deleted.append(item.name)
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted.append(item.name + "/")
            except Exception as e:
                logger.error("Failed to delete %s: %s", item, e)
    
    # 3. Clear cache
    _MODEL_CACHE.clear()
    _MODEL_CACHE_MTIME.clear()
    
    return {"status": "reset_complete", "deleted": deleted}

@app.post("/api/chat")
def api_chat(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Generate text from the trained model."""
    _check_request_origin(request)
    _require_admin(_admin)
    prompt = str(body.get("prompt","")).strip()
    if not prompt:
        return {"error": "Empty prompt"}
    if len(prompt) > MAX_PROMPT_CHARS:
        return {"error": f"Prompt too long. Max {MAX_PROMPT_CHARS} characters."}
    model_id = str(body.get("model_id") or body.get("model_path") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        candidate = Path(model_id)
        if candidate.exists() and _is_within(candidate, [OUTPUTS_DIR.resolve()]):
            model_path = candidate.resolve()
    if not model_path:
        return {"error": "Model path not allowed"}
    if not (Path(model_path)/"metadata.json").exists():
        return {"error": "No trained model found. Train first."}
    try:
        meta = _read_metadata(Path(model_path))
        readiness = _model_readiness(meta)
        core = _load_cached_model(Path(model_path))
        max_tokens = _clamp_int(body.get("max_tokens"), 40, 1, MAX_CHAT_TOKENS)
        temperature = _clamp_float(body.get("temperature"), 0.15, 0.0, 2.0)
        top_k = _clamp_int(body.get("top_k"), 5, 0, 100)
        chat_prompt = _format_mode_prompt(prompt, str(body.get("mode") or "chat"), body.get("system"))
        t0 = time.time()
        response = core.generate(
            chat_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_k=top_k,
        )
        response = _clean_chat_response(response)
        
        import re
        write_backs = [match.strip() for match in re.findall(r'<memory_start>(.*?)<memory_end>', response, re.DOTALL) if match.strip()]
        response_clean = re.sub(r'<memory_start>.*?<memory_end>', '', response, flags=re.DOTALL)
        response_clean = _clean_chat_response(response_clean)
        response_clean = re.sub(r'\n\s*\n', '\n', response_clean).strip()

        elapsed = time.time() - t0
        payload = {
            "response": response_clean or "[empty response]",
            "raw_response": response,
            "cortex_write_backs": write_backs,
            "time_sec": round(elapsed, 2),
            "model": model_id,
            "vocab_used": core.tokenizer.size,
            "readiness": readiness,
        }
        if hasattr(core, "get_routing_telemetry"):
            payload["routing_telemetry"] = core.get_routing_telemetry()
        if not readiness.get("ready"):
            payload["not_ready"] = True
            payload["warning"] = (
                "Raw checkpoint: "
                f"loss {readiness.get('loss', 'unknown')}, "
                f"train PPL {readiness.get('train_ppl', 'unknown')}. "
                "Output may be incoherent."
            )
        return payload
    except Exception as e:
        return {"error": str(e)}

# ── Cortex Explorer Endpoints ───────────────────────────────────────────

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

@app.get("/api/cortex/status")
def api_cortex_status(
    model_id: str = "latest",
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    res = _get_active_cortex(model_id)
    if not res:
        return {"exists": False, "size": 0, "dim": 0, "max_entries": 0}
    cortex, _, _ = res
    return {
        "exists": True,
        "size": cortex.size,
        "dim": cortex.config.dim,
        "max_entries": cortex.config.max_entries,
    }

@app.get("/api/cortex/entries")
def api_cortex_entries(
    model_id: str = "latest",
    topic: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    res = _get_active_cortex(model_id)
    if not res:
        return {"exists": False, "total": 0, "entries": []}
    cortex, _, _ = res
    
    entries = []
    for idx, e in enumerate(cortex.entries):
        if topic and topic.lower() not in e.topic.lower():
            continue
        if source and source.lower() not in e.source.lower():
            continue
        
        key_preview = e.key.tolist()[:5] if hasattr(e.key, "tolist") else []
        norm = float(e.key.norm().item()) if hasattr(e.key, "norm") else 0.0
        
        entries.append({
            "index": idx,
            "topic": e.topic,
            "source": e.source,
            "text": e.source,
            "preview": e.source[:60] + ("..." if len(e.source) > 60 else ""),
            "created_at": e.created_at,
            "access_count": e.access_count,
            "key_preview": key_preview,
            "key_norm": round(norm, 4),
            "norm": round(norm, 4),
        })
    
    total = len(entries)
    sliced = entries[offset:offset+limit]
    return {
        "exists": True,
        "total": total,
        "entries": sliced,
        "limit": limit,
        "offset": offset,
    }

@app.post("/api/cortex/search")
def api_cortex_search(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    model_id = str(body.get("model_id", "latest"))
    query_text = str(body.get("query", "")).strip()
    top_k = int(body.get("top_k", 10))
    
    if not query_text:
        return {"error": "Empty query text"}
        
    res = _get_active_cortex(model_id)
    if not res:
        return {"error": "Model or cortex not found"}
        
    cortex, _, core = res
    if cortex.size == 0:
        return {"entries": [], "query_tokens": []}
        
    import torch
    
    try:
        token_ids = core.encode(query_text, allow_growth=False)
        if not token_ids:
            return {"error": "Could not tokenize query or query yields no tokens."}
            
        with torch.no_grad():
            token_t = torch.tensor(token_ids, dtype=torch.long)
            embs = core.model.embedding(token_t)  # (seq_len, dim)
            query_vec = embs.mean(dim=0)          # (dim,)
            
            q_norm = torch.nn.functional.normalize(query_vec, dim=-1)
            keys = torch.stack([e.key for e in cortex.entries])  # (N, dim)
            keys_norm = torch.nn.functional.normalize(keys, dim=-1)
            
            scores = q_norm @ keys_norm.T  # (N,)
            
            top_k_actual = min(top_k, cortex.size)
            scores_vals, indices = torch.topk(scores, top_k_actual)
            
        results = []
        for score_val, idx_t in zip(scores_vals.tolist(), indices.tolist()):
            e = cortex.entries[idx_t]
            key_preview = e.key.tolist()[:5] if hasattr(e.key, "tolist") else []
            results.append({
                "index": idx_t,
                "score": round(score_val, 4),
                "topic": e.topic,
                "source": e.source,
                "text": e.source,
                "preview": e.source[:60] + ("..." if len(e.source) > 60 else ""),
                "created_at": e.created_at,
                "access_count": e.access_count,
                "key_preview": key_preview,
            })
            
            e.access_count += 1
            
        return {
            "entries": results,
            "results": results,
            "query_tokens": core.tokenizer.decode(token_ids),
        }
    except Exception as e:
        logger.error("Cortex similarity search failed: %s", e)
        return {"error": f"Search execution failed: {str(e)}"}

@app.post("/api/cortex/store")
def api_cortex_store(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    model_id = str(body.get("model_id", "latest"))
    text = str(body.get("text", "")).strip()
    topic = str(body.get("topic", "General")).strip()
    
    if not text:
        return {"error": "Empty text fact"}
        
    res = _get_active_cortex(model_id)
    if not res:
        return {"error": "Model or cortex not found"}
        
    cortex, model_path, core = res
    
    import torch
    
    try:
        token_ids = core.encode(text, allow_growth=False)
        if not token_ids:
            return {"error": "Could not tokenize text fact."}
            
        with torch.no_grad():
            token_t = torch.tensor(token_ids, dtype=torch.long)
            embs = core.model.embedding(token_t)  # (seq_len, dim)
            vector = embs.mean(dim=0)            # (dim,)
            
        index = cortex.store(key=vector, value=vector, topic=topic, source=text)
        cortex.save(model_path / "cortex")
        
        meta_file = model_path / "metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["cortex_entries"] = cortex.size
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            
        return {
            "status": "success",
            "index": index,
            "size": cortex.size,
            "topic": topic,
            "source": text[:80] + ("..." if len(text) > 80 else ""),
        }
    except Exception as e:
        logger.error("Failed to store vector fact in cortex: %s", e)
        return {"error": f"Failed to inject fact: {str(e)}"}

@app.delete("/api/cortex/delete")
def api_cortex_delete(
    request: Request,
    body: dict,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    model_id = str(body.get("model_id", "latest"))
    indices = body.get("indices")
    if indices is None and "index" in body:
        indices = body.get("index")
    topic = body.get("topic")
    wipe_all = bool(body.get("wipe_all", False))
    
    res = _get_active_cortex(model_id)
    if not res:
        return {"error": "Model or cortex not found"}
        
    cortex, model_path, core = res
    original_size = cortex.size
    
    try:
        if wipe_all:
            cortex.entries.clear()
            action = "wipe_all"
        elif indices is not None:
            if isinstance(indices, int):
                indices = [indices]
            idx_list = sorted([int(i) for i in indices], reverse=True)
            for idx in idx_list:
                if 0 <= idx < len(cortex.entries):
                    cortex.entries.pop(idx)
            action = "delete_indices"
        elif topic is not None:
            topic_str = str(topic).lower().strip()
            cortex.entries = [e for e in cortex.entries if topic_str not in e.topic.lower()]
            action = "prune_topic"
        else:
            return {"error": "Must specify either indices, topic, or wipe_all"}
            
        cortex.save(model_path / "cortex")
        if cortex.size == 0:
            for f in (model_path / "cortex" / "cortex_vectors.pt", model_path / "cortex" / "cortex_meta.json"):
                if f.exists():
                    f.unlink()
                    
        meta_file = model_path / "metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["cortex_entries"] = cortex.size
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            
        return {
            "status": "success",
            "action": action,
            "deleted_count": original_size - cortex.size,
            "remaining_size": cortex.size,
        }
    except Exception as e:
        logger.error("Failed to delete cortex entries: %s", e)
        return {"error": f"Deletion failed: {str(e)}"}

@app.post("/api/cortex/sleep_cycle")
def api_cortex_sleep_cycle(
    request: Request,
    body: dict,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    model_id = str(body.get("model_id", "latest"))
    similarity_threshold = float(body.get("similarity_threshold", 0.90))
    
    res = _get_active_cortex(model_id)
    if not res:
        return {"error": "Model or cortex not found"}
        
    cortex, model_path, core = res
    
    try:
        stats = cortex.sleep_cycle(similarity_threshold=similarity_threshold)
        cortex.save(model_path / "cortex")
        
        meta_file = model_path / "metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["cortex_entries"] = cortex.size
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            
        return {
            "status": "success",
            "stats": stats,
            "cortex_entries": cortex.size
        }
    except Exception as e:
        logger.error("Failed to run sleep cycle: %s", e)
        return {"error": f"Sleep cycle execution failed: {str(e)}"}

@app.post("/api/benchmark")
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
    if not (model_path/"metadata.json").exists():
        return {"error": "No model to benchmark"}
    try:
        meta = _read_metadata(model_path)
        data_path = body.get("data_path") or meta.get("train_data_path")
        if not data_path:
            latest_run = next((r for r in _read_run_history() if r.get("event") == "started"), {})
            data_name = latest_run.get("dataset")
            if data_name:
                data_path = next((str(p) for p in _dataset_index().values() if p.name == data_name), None)
        cmd = [sys.executable, str(_ROOT/"training"/"benchmark.py"),
                               "--model", str(model_path),
                               "--config", str(meta.get("train_config_name") or meta.get("config_name") or "seed"),
                               "--max-samples", str(_clamp_int(body.get("max_samples"), 32, 1, 512))]
        if data_path:
            benchmark_data = Path(str(data_path))
            if benchmark_data.exists() and _is_within(benchmark_data, _dashboard_roots()):
                cmd.extend(["--data", str(benchmark_data.resolve())])
        proc = subprocess.run(cmd,
                              capture_output=True, text=True, timeout=300, cwd=str(_ROOT))
        bp = model_path / "benchmark.json"
        if bp.exists():
            return {"status": "done", "results": json.loads(bp.read_text(encoding="utf-8"))}
        return {"error": proc.stderr or "Benchmark failed"}
    except Exception as e:
        return {"error": str(e)}

# ── WebSocket ────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if not _check_ws_origin(ws):
        await ws.close(code=1008)
        return
    if ws.query_params.get("token") != ADMIN_TOKEN:
        await ws.close(code=1008)
        return
    await ws.accept()
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    last_pos = 0
    log_f = OUTPUTS_DIR / "train.log"
    log_pos = 0
    if log_f.exists():
        with open(log_f, encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            log_pos = f.tell()
    if mf.exists():
        hist = []
        with open(mf, encoding="utf-8") as f:
            for line in f:
                if line.strip(): hist.append(json.loads(line))
            last_pos = f.tell()
        if hist: await ws.send_json({"type":"history","data":hist[-MAX_HISTORY_POINTS:]})
    else:
        await ws.send_json({
            "type": "training_state",
            "running": bool(_training_processes()),
            "status": _read_train_status(),
            "message": "Training process detected, but no live_metrics.jsonl has been written yet."
        })
    try:
        while True:
            await asyncio.sleep(0.8)
            # Also send system stats
            vm = psutil.virtual_memory()
            await ws.send_json({"type":"system","ram_pct":vm.percent,
                                "ram_avail_gb":round(vm.available/1e9,1),
                                "cpu_pct":psutil.cpu_percent(interval=0)})
            status = _read_train_status()
            if status:
                await ws.send_json({"type": "status", "data": status})
            if not mf.exists(): continue
            with open(mf, encoding="utf-8") as f:
                f.seek(last_pos)
                for line in f.readlines():
                    if line.strip():
                        await ws.send_json({"type":"metric","data":json.loads(line)})
                last_pos = f.tell()
            if log_f.exists():
                with open(log_f, encoding="utf-8", errors="replace") as f:
                    f.seek(log_pos)
                    for line in f.readlines():
                        if line.strip():
                            await ws.send_json({"type":"log", "data": line.strip()})
                    log_pos = f.tell()
            # Check if training ended
            global TRAIN_PROC
            if TRAIN_PROC and TRAIN_PROC.poll() is not None:
                await ws.send_json({"type":"train_done"})
                TRAIN_PROC = None
    except WebSocketDisconnect:
        pass

# ── Serve UI ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    p = _ROOT / "atulya" / "dashboard_ui.html"
    return HTMLResponse(p.read_text(encoding="utf-8") if p.exists() else "<h1>UI not found</h1>")


def _load_cached_model(model_path: Path):
    from atulya.core.npdna import NpDnaCore

    key = str(model_path.resolve())
    meta_path = model_path / "metadata.json"
    model_file = model_path / "model.pt"
    mtime = max(meta_path.stat().st_mtime, model_file.stat().st_mtime)
    if key not in _MODEL_CACHE or _MODEL_CACHE_MTIME.get(key) != mtime:
        _MODEL_CACHE[key] = NpDnaCore.load(model_path)
        _MODEL_CACHE_MTIME[key] = mtime
    return _MODEL_CACHE[key]

if __name__ == "__main__":
    print("\n  NP-DNA Command Center")
    print("  http://localhost:8501\n")
    if not os.environ.get("ATULYA_DASHBOARD_TOKEN"):
        print(f"  Session token: {ADMIN_TOKEN}")
        print(f"  Token source: {ADMIN_TOKEN_SOURCE}\n")
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="warning")
