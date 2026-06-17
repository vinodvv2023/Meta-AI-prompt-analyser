"""
main.py — FastAPI backend for the Meta AI Prompt Explorer.

Endpoints:
  GET  /search          - Search with filters (proxies to Meilisearch)
  GET  /tree            - Full tree metadata for left nav
  GET  /conversation/{id} - Full conversation by ID
  PATCH /conversation/{id}/favorite - Toggle favorite
  PATCH /conversation/{id}/tags     - Add/remove custom tags
  GET  /keywords        - All detected keywords grouped by category
  GET  /favorites       - All favorited conversations
  POST /ingest          - Trigger manual re-ingest
  GET  /stats           - Document counts by type
  GET  /health          - Health check
"""
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx

import meilisearch
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from ingestor import (
    get_client,
    setup_index,
    ingest_all,
    ingest_file,
    start_watcher,
    INDEX_NAME,
    SOURCE_DIR,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_watcher_observer = None

_keywords_cache = {"data": None, "ts": 0}
_KEYWORDS_TTL = 60


class FavoriteRequest(BaseModel):
    is_favorite: bool


class XxRequest(BaseModel):
    is_xx: bool


class XxxRequest(BaseModel):
    is_xxx: bool


class CustomPromptRequest(BaseModel):
    prompt: str
    ai_response: Optional[str] = ""
    type: Optional[str] = "image_prompt"
    label: Optional[str] = None
    date: Optional[str] = None
    is_xx: Optional[bool] = False
    is_xxx: Optional[bool] = False
    is_favorite: Optional[bool] = False


class TagsRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _watcher_observer
    client = get_client()
    setup_index(client)

    # Initial ingest in a background thread so the server starts immediately
    thread = threading.Thread(
        target=ingest_all,
        args=(str(SOURCE_DIR), client),
        daemon=True,
    )
    thread.start()

    # Continuous file watcher
    _watcher_observer = start_watcher(str(SOURCE_DIR), client)

    yield

    if _watcher_observer:
        _watcher_observer.stop()
        _watcher_observer.join()


app = FastAPI(title="Meta AI Prompt Explorer", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_filter(
    type_: Optional[str],
    mj: Optional[bool],
    failed: Optional[bool],
    has_video: Optional[bool],
    date: Optional[str],
    favorite: Optional[bool],
    tags: Optional[str],
    source: Optional[str],
    xx: Optional[bool] = None,
    xxx: Optional[bool] = None,
) -> Optional[str]:
    parts = []
    if type_:
        parts.append(f'type = "{type_}"')
    if mj is not None:
        parts.append(f'is_midjourney_style = {"true" if mj else "false"}')
    if failed is not None:
        parts.append(f'llm_failed = {"true" if failed else "false"}')
    if has_video is not None:
        parts.append(f'has_video = {"true" if has_video else "false"}')
    if date:
        parts.append(f'date = "{date}"')
    if favorite is not None:
        parts.append(f'is_favorite = {"true" if favorite else "false"}')
    if xx is not None:
        parts.append(f'is_xx = {"true" if xx else "false"}')
    if xxx is not None:
        parts.append(f'is_xxx = {"true" if xxx else "false"}')
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for tag in tag_list:
            parts.append(f'tags = "{tag}"')
    if source:
        parts.append(f'source_file = "{source}"')
    return " AND ".join(parts) if parts else None


@app.get("/search")
async def search(
    q: str = Query(default="", description="Search query"),
    type: Optional[str] = Query(default=None),
    mj: Optional[bool] = Query(default=None),
    failed: Optional[bool] = Query(default=None),
    has_video: Optional[bool] = Query(default=None),
    date: Optional[str] = Query(default=None),
    favorite: Optional[bool] = Query(default=None),
    tags: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    xx: Optional[bool] = Query(default=None),
    xxx: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
):
    client = get_client()
    index = client.get_index(INDEX_NAME)

    filter_str = _build_filter(type, mj, failed, has_video, date, favorite, tags, source, xx, xxx)

    params = {
        "limit": limit,
        "offset": offset,
        "attributesToHighlight": ["all_user_prompts", "all_ai_responses", "label"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
        "facets": ["type", "is_midjourney_style", "llm_failed", "has_video", "is_favorite", "is_xx", "is_xxx", "source_file"],
    }
    if filter_str:
        params["filter"] = filter_str

    try:
        result = index.search(q, params)
        return {
            "hits": result["hits"],
            "total": result.get("estimatedTotalHits", 0),
            "facets": result.get("facetDistribution"),
            "query": q,
            "offset": offset,
            "limit": limit,
        }
    except meilisearch.errors.MeilisearchApiError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/tree")
async def get_tree(
    type: Optional[str] = Query(default=None),
    mj: Optional[bool] = Query(default=None),
    failed: Optional[bool] = Query(default=None),
    favorite: Optional[bool] = Query(default=None),
    tags: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    xx: Optional[bool] = Query(default=None),
    xxx: Optional[bool] = Query(default=None),
):
    """Return tree metadata for the left nav: { date: [{ id, label, type, ... }] }"""
    client = get_client()
    index = client.get_index(INDEX_NAME)

    filter_str = _build_filter(type, mj, failed, None, None, favorite, tags, source, xx, xxx)
    if filter_str:
        filter_str = f'(type != "media") AND ({filter_str})'
    else:
        filter_str = 'type != "media"'

    all_docs = []
    offset = 0
    batch = 1000
    fields = ["id", "date", "label", "type", "is_midjourney_style", "has_video",
               "llm_failed", "all_user_prompts", "is_favorite", "is_xx", "is_xxx", "source_file"]

    while True:
        params: dict = {"limit": batch, "offset": offset, "fields": fields}
        if filter_str:
            params["filter"] = filter_str
        result = index.get_documents(params)
        chunk = result.results
        all_docs.extend(chunk)
        if len(chunk) < batch:
            break
        offset += batch

    tree: dict = {}
    for doc in all_docs:
        date = getattr(doc, "date", None) or (doc["date"] if isinstance(doc, dict) and "date" in doc else "Unknown")
        if date not in tree:
            tree[date] = []
        d = doc if isinstance(doc, dict) else dict(doc)
        preview = (d.get("all_user_prompts") or "")[:100]
        tree[date].append({
            "id": d.get("id"),
            "label": d.get("label", ""),
            "type": d.get("type", "conversation"),
            "is_midjourney_style": d.get("is_midjourney_style", False),
            "has_video": d.get("has_video", False),
            "llm_failed": d.get("llm_failed", False),
            "is_favorite": d.get("is_favorite", False),
            "is_xx": d.get("is_xx", False),
            "is_xxx": d.get("is_xxx", False),
            "source_file": d.get("source_file", ""),
            "preview": preview,
        })

    return dict(sorted(tree.items(), key=lambda x: x[0], reverse=True))


@app.get("/conversation/{doc_id}")
async def get_conversation(doc_id: str):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        return doc
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.post("/ingest")
async def trigger_ingest(background_tasks: BackgroundTasks):
    client = get_client()
    background_tasks.add_task(ingest_all, str(SOURCE_DIR), client)
    return {"message": "Re-ingest started in background"}


THREADS_API_URL = os.getenv("THREADS_API_URL", "http://localhost:8002")


@app.post("/extract-threads")
async def extract_threads():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{THREADS_API_URL}/export", timeout=30.0)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            data = r.json()
            
            # Synchronously ingest the updated threads prompts file
            from ingestor import ingest_file, get_client
            threads_file = SOURCE_DIR / "threads-prompts.json"
            ingested_count = ingest_file(str(threads_file), get_client())
            
            return {
                "status": "success",
                "exported_count": data.get("count"),
                "ingested_count": ingested_count,
                "message": f"Successfully extracted {data.get('count')} prompts and ingested {ingested_count} into Meilisearch."
            }
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Failed to connect to Threads API: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


@app.get("/stats")
async def get_stats():
    client = get_client()
    index = client.get_index(INDEX_NAME)

    stats = index.get_stats()
    facet_result = index.search("", {
        "facets": ["type", "is_midjourney_style", "llm_failed", "has_video", "is_favorite", "is_xx", "is_xxx", "source_file"],
        "limit": 0,
    })

    # Check if Threads API is live
    threads_live = False
    try:
        async with httpx.AsyncClient() as hc:
            res = await hc.get(f"{THREADS_API_URL}/health", timeout=0.8)
            threads_live = (res.status_code == 200)
    except Exception:
        pass

    return {
        "total_documents": stats.number_of_documents,
        "facets": facet_result.get("facetDistribution"),
        "threads_api_live": threads_live
    }


@app.get("/health")
async def health():
    client = get_client()
    try:
        h = client.health()
        return {"status": "ok", "meilisearch": h.status}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


from typing import Any

def _update_custom_prompt_file_field(doc_id: str, field: str, value: Any):
    import json
    file_path = SOURCE_DIR / "user-prompts.json"
    if not file_path.exists():
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)

        updated = False
        for p in prompts:
            if p.get("id") == doc_id:
                p[field] = value
                updated = True
                break

        if updated:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(prompts, f, indent=2)
    except Exception as e:
        logger.error(f"Error updating user-prompts.json field {field} for doc {doc_id}: {e}")


def _save_custom_prompt(entry: CustomPromptRequest) -> dict:
    import json
    from datetime import datetime
    import hashlib
    import random

    file_path = SOURCE_DIR / "user-prompts.json"

    # Load existing prompts
    prompts = []
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                prompts = json.load(f)
        except Exception:
            prompts = []

    # Create new record
    date_str = entry.date or datetime.now().strftime("%Y-%m-%d")
    prompt_text = entry.prompt.strip()

    # Generate stable id
    doc_id = hashlib.sha256(f"user:{date_str}:{prompt_text[:200]}".encode()).hexdigest()[:16]

    # Handle collisions
    existing_ids = {p.get("id") for p in prompts if "id" in p}
    if doc_id in existing_ids:
        doc_id = hashlib.sha256(f"user:{date_str}:{prompt_text[:200]}:{random.random()}".encode()).hexdigest()[:16]

    label_str = entry.label or f"User Prompt {date_str}"

    new_prompt = {
        "id": doc_id,
        "label": label_str,
        "prompt": prompt_text,
        "ai_response": entry.ai_response or "",
        "type": entry.type or "image_prompt",
        "date": date_str,
        "is_favorite": entry.is_favorite or False,
        "is_xx": entry.is_xx or False,
        "is_xxx": entry.is_xxx or False,
    }

    prompts.append(new_prompt)

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2)

    return new_prompt


@app.patch("/conversation/{doc_id}/favorite")
async def toggle_favorite(doc_id: str, body: FavoriteRequest):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        d = doc if isinstance(doc, dict) else dict(doc)
        d["is_favorite"] = body.is_favorite
        index.update_documents([d])

        if d.get("source_file") == "user-prompts.json":
            _update_custom_prompt_file_field(doc_id, "is_favorite", body.is_favorite)

        return {"id": doc_id, "is_favorite": body.is_favorite}
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.patch("/conversation/{doc_id}/xx")
async def toggle_xx(doc_id: str, body: XxRequest):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        d = doc if isinstance(doc, dict) else dict(doc)
        d["is_xx"] = body.is_xx
        index.update_documents([d])

        if d.get("source_file") == "user-prompts.json":
            _update_custom_prompt_file_field(doc_id, "is_xx", body.is_xx)

        return {"id": doc_id, "is_xx": body.is_xx}
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.patch("/conversation/{doc_id}/xxx")
async def toggle_xxx(doc_id: str, body: XxxRequest):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        d = doc if isinstance(doc, dict) else dict(doc)
        d["is_xxx"] = body.is_xxx
        index.update_documents([d])

        if d.get("source_file") == "user-prompts.json":
            _update_custom_prompt_file_field(doc_id, "is_xxx", body.is_xxx)

        return {"id": doc_id, "is_xxx": body.is_xxx}
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.post("/conversation/custom")
async def create_custom_prompt(body: CustomPromptRequest):
    try:
        new_prompt_doc = _save_custom_prompt(body)

        # Synchronously ingest so Meilisearch is updated immediately
        client = get_client()
        ingest_file(str(SOURCE_DIR / "user-prompts.json"), client)

        return new_prompt_doc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/conversation/{doc_id}/tags")
async def update_tags(doc_id: str, body: TagsRequest):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        d = doc if isinstance(doc, dict) else dict(doc)

        custom = set(d.get("custom_tags", []) or [])
        for tag in body.add:
            custom.add(tag)
        for tag in body.remove:
            custom.discard(tag)

        d["custom_tags"] = sorted(custom)

        detected = d.get("detected_categories", {}) or {}
        auto_tags = []
        seen = set()
        for kw_list in detected.values():
            for kw in kw_list:
                if kw not in seen:
                    seen.add(kw)
                    auto_tags.append(kw)

        d["tags"] = auto_tags + [t for t in sorted(custom) if t not in seen]

        index.update_documents([d])
        return {"id": doc_id, "tags": d["tags"], "custom_tags": d["custom_tags"]}
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.get("/keywords")
async def get_keywords():
    global _keywords_cache
    now = time.time()
    if _keywords_cache["data"] and (now - _keywords_cache["ts"]) < _KEYWORDS_TTL:
        return _keywords_cache["data"]

    client = get_client()
    index = client.get_index(INDEX_NAME)

    all_docs = []
    offset = 0
    batch = 1000
    fields = ["detected_categories"]

    while True:
        params: dict = {"limit": batch, "offset": offset, "fields": fields}
        result = index.get_documents(params)
        chunk = result.results
        all_docs.extend(chunk)
        if len(chunk) < batch:
            break
        offset += batch

    categories = {
        "medium_style": {},
        "lighting": {},
        "composition": {},
        "color_palette": {},
        "environment": {},
        "artist_reference": {},
    }

    for doc in all_docs:
        d = doc if isinstance(doc, dict) else dict(doc)
        cats = d.get("detected_categories", {}) or {}
        for cat, keywords in cats.items():
            if cat not in categories:
                categories[cat] = {}
            for kw in keywords:
                categories[cat][kw] = categories[cat].get(kw, 0) + 1

    sorted_categories = {}
    for cat, kw_counts in categories.items():
        sorted_categories[cat] = dict(sorted(kw_counts.items(), key=lambda x: x[1], reverse=True))

    _keywords_cache = {"data": sorted_categories, "ts": now}
    return sorted_categories


@app.get("/favorites")
async def get_favorites():
    client = get_client()
    index = client.get_index(INDEX_NAME)

    filter_str = "is_favorite = true"
    all_docs = []
    offset = 0
    batch = 1000
    fields = ["id", "date", "label", "type", "all_user_prompts",
              "is_midjourney_style", "has_video", "llm_failed"]

    while True:
        params: dict = {"limit": batch, "offset": offset, "fields": fields, "filter": filter_str}
        result = index.get_documents(params)
        chunk = result.results
        all_docs.extend(chunk)
        if len(chunk) < batch:
            break
        offset += batch

    return [doc if isinstance(doc, dict) else dict(doc) for doc in all_docs]


def _delete_custom_prompt_from_file(doc_id: str):
    import json
    file_path = SOURCE_DIR / "user-prompts.json"
    if not file_path.exists():
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
        
        updated_prompts = [p for p in prompts if p.get("id") != doc_id]
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(updated_prompts, f, indent=2)
    except Exception as e:
        logger.error(f"Error deleting user prompt {doc_id} from JSON: {e}")


def _delete_threads_prompt_from_file(doc_id: str):
    import json
    import hashlib
    file_path = SOURCE_DIR / "threads-prompts.json"
    if not file_path.exists():
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        updated_entries = []
        label_values = data.get("label_values", [])
        if label_values and label_values[0].get("dict"):
            dict_outer = label_values[0]["dict"]
            if dict_outer and dict_outer[0].get("dict"):
                entries = dict_outer[0]["dict"]
                for entry in entries:
                    label = entry.get("label", "")
                    value = entry.get("value", "")
                    entry_id = hashlib.sha256(f"threads:{label}:{value[:200]}".encode()).hexdigest()[:16]
                    if entry_id != doc_id:
                        updated_entries.append(entry)
                
                dict_outer[0]["dict"] = updated_entries
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error deleting threads prompt {doc_id} from JSON: {e}")


@app.delete("/conversation/{doc_id}")
async def delete_conversation(doc_id: str):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        d = doc if isinstance(doc, dict) else dict(doc)
        source_file = d.get("source_file")
        
        # Delete from Meilisearch
        index.delete_document(doc_id)
        
        # Delete from local files
        if source_file == "user-prompts.json":
            _delete_custom_prompt_from_file(doc_id)
        elif source_file == "threads-prompts.json":
            _delete_threads_prompt_from_file(doc_id)
            
        return {"status": "success", "message": f"Prompt {doc_id} deleted successfully."}
    except meilisearch.errors.MeilisearchApiError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found or failed to delete")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
