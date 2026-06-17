"""
threads_api.py — FastAPI service that serves image prompts from multiple Threads SQLite databases.

Features:
  - Multi-DB aggregation (THREADS_DB_PATHS, pipe-separated)
  - Auto-export: polls DBs every N seconds, re-exports to source/ when row count changes
  - The existing backend file watcher then auto-ingests the updated JSON into Meilisearch

Run:
    uvicorn threads_service.api:app --port 8002 --reload
"""
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DB_PATHS = [
    p.strip()
    for p in os.getenv(
        "THREADS_DB_PATHS",
        r"C:\Users\xtrem\Downloads\python_proj\threads\docs\docs\prompts_backup\prompts.db"
        r"|C:\Users\xtrem\Downloads\python_proj\threads\data\prompts.db",
    ).split("|")
    if p.strip() and os.path.isfile(p.strip())
]

app = FastAPI(title="Threads Image Prompts API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_conn(db_index: int = 0) -> sqlite3.Connection:
    path = DB_PATHS[db_index]
    conn = sqlite3.connect(path)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    conn.row_factory = sqlite3.Row
    return conn


def _query_all_dbs(query: str, params: tuple = ()) -> list:
    all_rows = []
    for i, db_path in enumerate(DB_PATHS):
        conn = _get_conn(i)
        try:
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                d = dict(r)
                d["_db_index"] = i
                d["_db_path"] = db_path
                all_rows.append(d)
        finally:
            conn.close()
    return all_rows


class PromptOut(BaseModel):
    id: int
    user_id: int
    thread_url: str
    post_url: Optional[str] = None
    post_text: Optional[str] = None
    extracted_prompt: Optional[str] = None
    prompt_type: Optional[str] = None
    is_reply: int = 0
    parent_post_id: Optional[int] = None
    post_date: Optional[str] = None
    has_image: int = 0
    has_video: int = 0
    cleaned_prompt: Optional[str] = None
    scraped_at: Optional[str] = None


class DbStats(BaseModel):
    db_path: str
    total: int
    image_prompts: int
    users: int


class PromptSummary(BaseModel):
    total: int
    image_prompts: int
    users: int
    databases: List[DbStats]


@app.get("/health")
def health():
    return {"status": "ok", "databases": DB_PATHS}


@app.get("/stats", response_model=PromptSummary)
def stats():
    db_stats = []
    grand_total = 0
    grand_image = 0
    all_users = set()

    for i, db_path in enumerate(DB_PATHS):
        conn = _get_conn(i)
        cur = conn.cursor()
        total = cur.execute("SELECT count(*) FROM posts").fetchone()[0]
        image = cur.execute("SELECT count(*) FROM posts WHERE prompt_type = 'image'").fetchone()[0]
        user_rows = cur.execute("SELECT DISTINCT user_id FROM posts").fetchall()
        conn.close()

        users = len(user_rows)
        grand_total += total
        grand_image += image
        db_stats.append(DbStats(db_path=str(db_path), total=total, image_prompts=image, users=users))

    return PromptSummary(
        total=grand_total,
        image_prompts=grand_image,
        users=len(db_stats),
        databases=db_stats,
    )


@app.get("/prompts", response_model=List[PromptOut])
def get_prompts(
    user_id: Optional[int] = Query(default=None),
    prompt_type: Optional[str] = Query(default=None),
    has_image: Optional[int] = Query(default=None),
    has_video: Optional[int] = Query(default=None),
    db: Optional[int] = Query(default=None, description="DB index (0-based). Omit for all."),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
):
    clauses = []
    params = []
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(user_id)
    if prompt_type is not None:
        clauses.append("prompt_type = ?")
        params.append(prompt_type)
    if has_image is not None:
        clauses.append("has_image = ?")
        params.append(has_image)
    if has_video is not None:
        clauses.append("has_video = ?")
        params.append(has_video)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM posts{where} ORDER BY id"

    indices = [db] if db is not None and 0 <= db < len(DB_PATHS) else list(range(len(DB_PATHS)))

    all_rows = []
    for i in indices:
        conn = _get_conn(i)
        try:
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                all_rows.append(dict(r))
        finally:
            conn.close()

    return all_rows[offset : offset + limit]


@app.get("/prompts/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: int, db: Optional[int] = Query(default=None)):
    indices = [db] if db is not None and 0 <= db < len(DB_PATHS) else list(range(len(DB_PATHS)))

    for i in indices:
        conn = _get_conn(i)
        try:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (prompt_id,)).fetchone()
            if row:
                conn.close()
                return dict(row)
        finally:
            if conn:
                conn.close()

    raise HTTPException(status_code=404, detail="Prompt not found")


@app.get("/users", response_model=List[dict])
def get_users():
    all_rows = []
    for i, db_path in enumerate(DB_PATHS):
        conn = _get_conn(i)
        try:
            rows = conn.execute(
                "SELECT user_id, count(*) as post_count FROM posts GROUP BY user_id ORDER BY post_count DESC"
            ).fetchall()
            for r in rows:
                d = dict(r)
                d["db_index"] = i
                all_rows.append(d)
        finally:
            conn.close()
    return all_rows


@app.post("/export")
def export_prompts():
    try:
        count = _export_to_source()
        return {"status": "success", "count": count, "message": f"Successfully exported {count} prompts."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Auto-export watcher ──────────────────────────────────────────────────

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "source")
EXPORT_FILE = os.path.join(SOURCE_DIR, "threads-prompts.json")
AUTO_EXPORT_INTERVAL = int(os.getenv("THREADS_AUTO_EXPORT_INTERVAL", "30"))

_last_counts: dict[str, int] = {}


def _get_row_counts() -> dict[str, int]:
    counts = {}
    for i, db_path in enumerate(DB_PATHS):
        conn = _get_conn(i)
        try:
            count = conn.execute("SELECT count(*) FROM posts").fetchone()[0]
            counts[db_path] = count
        finally:
            conn.close()
    return counts


def _export_to_source():
    all_rows = []
    for i, db_path in enumerate(DB_PATHS):
        conn = _get_conn(i)
        try:
            rows = conn.execute(
                "SELECT * FROM posts WHERE prompt_type = 'image' ORDER BY id"
            ).fetchall()
            all_rows.extend(dict(r) for r in rows)
        finally:
            conn.close()

    entries = []
    for row in all_rows:
        prompt_text = row.get("extracted_prompt") or ""
        if not prompt_text.strip():
            continue
        entries.append({
            "label": f"Threads_{row.get('user_id', '')}_{row.get('id', 'unknown')}",
            "value": f"Thread Post\n\nYou: {prompt_text}\nThread AI: [Image generated from prompt]",
            "thread_url": row.get("thread_url", ""),
            "user_id": row.get("user_id", ""),
            "has_image": row.get("has_image", 0),
            "has_video": row.get("has_video", 0),
            "prompt_type": row.get("prompt_type", ""),
        })

    output = {
        "media": [],
        "label_values": [{
            "label": "Threads prompts",
            "dict": [{"label": "threads", "dict": entries}],
        }],
    }

    os.makedirs(SOURCE_DIR, exist_ok=True)
    with open(EXPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return len(entries)


def _auto_export_loop():
    global _last_counts
    _last_counts = _get_row_counts()
    logger.info(f"Auto-export watcher started (interval={AUTO_EXPORT_INTERVAL}s, DBs={len(DB_PATHS)})")

    while True:
        time.sleep(AUTO_EXPORT_INTERVAL)
        try:
            current = _get_row_counts()
            if current != _last_counts:
                old_total = sum(_last_counts.values())
                new_total = sum(current.values())
                logger.info(f"DB change detected: {old_total} -> {new_total} rows. Re-exporting...")
                count = _export_to_source()
                _last_counts = current
                logger.info(f"Exported {count} prompts to {EXPORT_FILE}")
        except Exception as exc:
            logger.error(f"Auto-export error: {exc}")


@app.on_event("startup")
def _start_watcher():
    try:
        count = _export_to_source()
        logger.info(f"Initial export on startup: exported {count} prompts to {EXPORT_FILE}")
    except Exception as exc:
        logger.error(f"Failed initial export on startup: {exc}")
    t = threading.Thread(target=_auto_export_loop, daemon=True)
    t.start()
