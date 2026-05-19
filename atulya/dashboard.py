"""NP-DNA Command Center — Production Admin Panel.

All-in-one: train, chat, monitor, manage checkpoints.
Runs training as subprocess, streams metrics via WebSocket.

Usage:  python atulya/dashboard.py
        Open http://localhost:8501
"""
from __future__ import annotations
import asyncio, json, logging, os, subprocess, sys, time
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
MAX_PROMPT_CHARS = int(os.environ.get("ATULYA_DASHBOARD_MAX_PROMPT_CHARS", "4000"))
MAX_CHAT_TOKENS = int(os.environ.get("ATULYA_DASHBOARD_MAX_TOKENS", "256"))
MAX_HISTORY_POINTS = int(os.environ.get("ATULYA_DASHBOARD_HISTORY", "1000"))
ADMIN_TOKEN = os.environ.get("ATULYA_DASHBOARD_TOKEN", "admin").strip()
DEFAULT_SYSTEM_PROMPT = "You are Atulya. Be warm, thoughtful, and direct."


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
        roots.append(Path(r"F:\datasets"))
    return [p.resolve() for p in roots if p.exists()]


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
    system = (system or DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT
    if "Assistant:" in prompt or "User:" in prompt:
        return prompt
    return f"System: {system}\nUser: {prompt}\nAssistant:"


def _clean_chat_response(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    for marker in ("\nUser:", "\nSystem:", "\nContext:", "\nAssistant:"):
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx].strip()
    return text


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
        best_loss = min(m.get("losses", [999])) if m.get("losses") else 999
        ckpts.append({"id": "latest", "label": "latest",
                       "config": m.get("config_name","?"), "step": len(m.get("losses",[])),
                       "best_loss": round(best_loss,4), "params": m.get("parameter_count",0),
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
            best_loss = min(m.get("losses",[999])) if m.get("losses") else 999
            ckpts.append({"id": d.name, "label": d.name,
                           "config": m.get("config_name","?"), "step": len(m.get("losses",[])),
                           "best_loss": round(best_loss,4), "params": m.get("parameter_count",0),
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
    return {"ram_total_gb": round(vm.total/1e9,1), "ram_avail_gb": round(vm.available/1e9,1),
            "ram_pct": vm.percent, "cpu_pct": cpu, "cpu_count": psutil.cpu_count()}

@app.get("/api/model")
def api_model(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    meta_p = OUTPUTS_DIR / "metadata.json"
    if not meta_p.exists():
        return {"exists": False}
    m = json.loads(meta_p.read_text(encoding="utf-8"))
    bench_p = OUTPUTS_DIR / "benchmark.json"
    bench = json.loads(bench_p.read_text(encoding="utf-8")) if bench_p.exists() else None
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
        
    ckpt_dir = OUTPUTS_DIR / "checkpoints" / model_id
    if not ckpt_dir.exists() or not ckpt_dir.is_dir():
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
    lr = _clamp_float(body.get("lr"), 2e-3, 1e-6, 1.0)
    # Clear old live metrics
    mf = OUTPUTS_DIR / "live_metrics.jsonl"
    mf.parent.mkdir(parents=True, exist_ok=True)
    if mf.exists(): mf.unlink()
    status_file = OUTPUTS_DIR / "train_status.json"
    if status_file.exists(): status_file.unlink()
    cmd = [sys.executable, str(_ROOT/"training"/"npdna_train.py"),
           "--config", config, "--steps", str(steps),
           "--lr", str(lr), "--data", str(data_path),
           "--limit", str(limit), "--log-every", "5",
           "--checkpoint-every", str(checkpoint_every),
           "--device", "auto",
           "--bpe-merges", str(_clamp_int(body.get("bpe_merges"), 1000, 0, 8000))]
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
        core = _load_cached_model(Path(model_path))
        max_tokens = _clamp_int(body.get("max_tokens"), 80, 1, MAX_CHAT_TOKENS)
        temperature = _clamp_float(body.get("temperature"), 0.35, 0.0, 2.0)
        top_k = _clamp_int(body.get("top_k"), 12, 0, 100)
        chat_prompt = _format_chat_prompt(prompt, body.get("system"))
        t0 = time.time()
        response = core.generate(
            chat_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_k=top_k,
        )
        response = _clean_chat_response(response)
        elapsed = time.time() - t0
        return {"response": response, "time_sec": round(elapsed,2),
                "model": model_id, "vocab_used": core.tokenizer.size}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/benchmark")
def api_run_benchmark(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Run benchmark on current model."""
    _check_request_origin(request)
    _require_admin(_admin)
    if not (OUTPUTS_DIR/"metadata.json").exists():
        return {"error": "No model to benchmark"}
    try:
        proc = subprocess.run([sys.executable, str(_ROOT/"training"/"benchmark.py"),
                               "--model", str(OUTPUTS_DIR), "--config", "nano"],
                              capture_output=True, text=True, timeout=120, cwd=str(_ROOT))
        bp = OUTPUTS_DIR / "benchmark.json"
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
    if not ADMIN_TOKEN or ws.query_params.get("token") != ADMIN_TOKEN:
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
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="warning")
