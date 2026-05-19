"""NP-DNA Dashboard Memory Cortex Routes.
"""
from __future__ import annotations
import json
import logging
from fastapi import APIRouter, Header, Request, HTTPException

from atulya.dashboard.helpers import (
    _require_admin,
    _check_request_origin,
    _get_active_cortex,
)

logger = logging.getLogger("atulya.dashboard.routes.cortex")
router = APIRouter()


@router.get("/api/cortex/status")
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


@router.get("/api/cortex/entries")
def api_cortex_entries(
    model_id: str = "latest",
    topic: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    page: int | None = None,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _require_admin(_admin)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    if page is not None and offset == 0:
        offset = page * limit
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
    sliced = entries[offset : offset + limit]
    return {
        "exists": True,
        "total": total,
        "entries": sliced,
        "limit": limit,
        "offset": offset,
    }


@router.post("/api/cortex/search")
def api_cortex_search(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    model_id = str(body.get("model_id", "latest"))
    query_text = str(body.get("query", "")).strip()
    top_k = max(1, min(int(body.get("top_k", 10)), 100))
    
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


@router.post("/api/cortex/store")
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
    if len(text) > 4000:
        return {"error": "Text fact too long. Max 4000 characters."}
        
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


@router.delete("/api/cortex/delete")
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
            for f in (
                model_path / "cortex" / "cortex_vectors.pt",
                model_path / "cortex" / "cortex_meta.json",
            ):
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


@router.post("/api/cortex/sleep_cycle")
def api_cortex_sleep_cycle(
    request: Request,
    body: dict,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    
    model_id = str(body.get("model_id", "latest"))
    try:
        similarity_threshold = float(body.get("similarity_threshold", 0.90))
    except (ValueError, TypeError):
        similarity_threshold = 0.90
    similarity_threshold = max(0.0, min(similarity_threshold, 1.0))
    
    res = _get_active_cortex(model_id)
    if not res:
        return {"error": "Model or cortex not found"}
        
    cortex, model_path, core = res
    
    try:
        stats = cortex.sleep_cycle(similarity_threshold=similarity_threshold, core=core)
        cortex.save(model_path / "cortex")
        
        meta_file = model_path / "metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["cortex_entries"] = cortex.size
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            
        return {
            "status": "success",
            "stats": stats,
            "cortex_entries": cortex.size,
        }
    except Exception as e:
        logger.error("Failed to run sleep cycle: %s", e)
        return {"error": f"Sleep cycle execution failed: {str(e)}"}
