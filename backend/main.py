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
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

import meilisearch
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from ingestor import (
    get_client,
    setup_index,
    ingest_all,
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
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for tag in tag_list:
            parts.append(f'tags = "{tag}"')
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
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
):
    client = get_client()
    index = client.get_index(INDEX_NAME)

    filter_str = _build_filter(type, mj, failed, has_video, date, favorite, tags)

    params = {
        "limit": limit,
        "offset": offset,
        "attributesToHighlight": ["all_user_prompts", "all_ai_responses", "label"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
        "facets": ["type", "is_midjourney_style", "llm_failed", "has_video", "is_favorite"],
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
):
    """Return tree metadata for the left nav: { date: [{ id, label, type, ... }] }"""
    client = get_client()
    index = client.get_index(INDEX_NAME)

    filter_str = _build_filter(type, mj, failed, None, None, favorite, tags)

    all_docs = []
    offset = 0
    batch = 1000
    fields = ["id", "date", "label", "type", "is_midjourney_style", "has_video",
              "llm_failed", "all_user_prompts", "is_favorite"]

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


@app.get("/stats")
async def get_stats():
    client = get_client()
    index = client.get_index(INDEX_NAME)

    stats = index.get_stats()
    facet_result = index.search("", {
        "facets": ["type", "is_midjourney_style", "llm_failed", "has_video", "is_favorite"],
        "limit": 0,
    })
    return {
        "total_documents": stats.number_of_documents,
        "facets": facet_result.get("facetDistribution"),
    }


@app.get("/health")
async def health():
    client = get_client()
    try:
        h = client.health()
        return {"status": "ok", "meilisearch": h.status}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.patch("/conversation/{doc_id}/favorite")
async def toggle_favorite(doc_id: str, body: FavoriteRequest):
    client = get_client()
    index = client.get_index(INDEX_NAME)
    try:
        doc = index.get_document(doc_id)
        d = doc if isinstance(doc, dict) else dict(doc)
        d["is_favorite"] = body.is_favorite
        index.update_documents([d])
        return {"id": doc_id, "is_favorite": body.is_favorite}
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=404, detail="Conversation not found")


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
