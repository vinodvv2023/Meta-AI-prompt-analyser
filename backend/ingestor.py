"""
ingestor.py — Parse JSON files, classify documents, and index into Meilisearch.
Also starts a watchdog file watcher for continuous ingestion from the source/ folder.
"""
import os
import time
import logging
from pathlib import Path
from typing import Optional

import meilisearch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

from parser import parse_json_file
from classifier import classify_document

load_dotenv()

logger = logging.getLogger(__name__)

MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey123")
INDEX_NAME = "conversations"

# Path to the source JSON folder (one level up from this backend/ folder)
SOURCE_DIR = Path(__file__).parent.parent / "source"


# ─── Meilisearch Client ───────────────────────────────────────────────────

def get_client() -> meilisearch.Client:
    return meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)


def _wait_for_meilisearch(client: meilisearch.Client, timeout: int = 30) -> None:
    """Block until Meilisearch is reachable, retrying once per second."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            client.health()
            logger.info("✅ Meilisearch is ready.")
            return
        except Exception:
            logger.info("⏳ Waiting for Meilisearch to start…")
            time.sleep(1)
    raise RuntimeError(f"Meilisearch not reachable at {MEILI_URL} after {timeout}s")


def setup_index(client: meilisearch.Client) -> meilisearch.index.Index:
    """Ensure the index exists and is configured with the right settings."""
    _wait_for_meilisearch(client)  # Blocks until Meilisearch is up

    try:
        index = client.get_index(INDEX_NAME)
        logger.info(f"Index '{INDEX_NAME}' already exists.")
    except Exception:
        # Index doesn't exist yet — create it and wait for the async task
        logger.info(f"Creating index '{INDEX_NAME}'…")
        task = client.create_index(INDEX_NAME, {"primaryKey": "id"})
        # task_uid confirmed as the correct attribute in SDK 0.31.0
        task_uid = task.task_uid if hasattr(task, "task_uid") else task.uid
        client.wait_for_task(task_uid, timeout_in_ms=10_000)
        index = client.get_index(INDEX_NAME)

    index.update_settings({
        "searchableAttributes": [
            "all_user_prompts",
            "all_ai_responses",
            "label",
            "tags",
            "custom_tags",
        ],
        "filterableAttributes": [
            "type",
            "is_midjourney_style",
            "llm_failed",
            "date",
            "has_video",
            "source_file",
            "is_favorite",
            "tags",
            "custom_tags",
        ],
        "sortableAttributes": ["date"],
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
            "sort",
            "exactness",
        ],
    })

    return index




# ─── Ingestion ────────────────────────────────────────────────────────────

def ingest_file(filepath: str, client: Optional[meilisearch.Client] = None) -> int:
    """Parse, classify, and index a single JSON file. Returns number of docs ingested."""
    if client is None:
        client = get_client()

    logger.info(f"📂 Ingesting: {filepath}")

    try:
        documents = parse_json_file(filepath)
    except Exception as exc:
        logger.error(f"Parse error for {filepath}: {exc}")
        return 0

    classified = [classify_document(doc) for doc in documents if doc]
    classified = [d for d in classified if d]

    if not classified:
        logger.warning(f"No documents parsed from {filepath}")
        return 0

    index = setup_index(client)

    existing_docs = {}
    try:
        ids = [d["id"] for d in classified]
        if ids:
            for i in range(0, len(ids), 1000):
                batch_ids = ids[i:i+1000]
                results = index.get_documents({"filter": None, "fields": ["id", "custom_tags", "is_favorite"], "limit": 1000})
                for r in results.results:
                    rd = r if isinstance(r, dict) else dict(r)
                    existing_docs[rd.get("id")] = rd
    except Exception:
        pass

    for d in classified:
        doc_id = d["id"]
        if doc_id in existing_docs:
            existing = existing_docs[doc_id]
            d["custom_tags"] = existing.get("custom_tags", []) or []
            d["is_favorite"] = existing.get("is_favorite", False)

    batch_size = 500
    total = 0
    for i in range(0, len(classified), batch_size):
        batch = classified[i : i + batch_size]
        index.add_documents(batch)
        total += len(batch)
        logger.info(f"  → Indexed {total}/{len(classified)} documents")

    logger.info(f"✅ Done: {total} documents from {Path(filepath).name}")
    return total


def ingest_all(source_dir: Optional[str] = None, client: Optional[meilisearch.Client] = None) -> int:
    """Ingest all .json files from source_dir."""
    path = Path(source_dir) if source_dir else SOURCE_DIR
    if client is None:
        client = get_client()

    json_files = list(path.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {path}")
        return 0

    total = 0
    for fp in json_files:
        total += ingest_file(str(fp), client)
    return total


# ─── Watchdog File Watcher ────────────────────────────────────────────────

class _JsonWatchHandler(FileSystemEventHandler):
    def __init__(self, client: meilisearch.Client):
        self._client = client
        self._debounce: dict = {}

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self._process(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            now = time.time()
            if now - self._debounce.get(event.src_path, 0) > 5:
                self._debounce[event.src_path] = now
                self._process(event.src_path)

    def _process(self, filepath: str):
        logger.info(f"👁 File change detected: {filepath}")
        ingest_file(filepath, self._client)


def start_watcher(source_dir: Optional[str] = None, client: Optional[meilisearch.Client] = None) -> Observer:
    path = str(Path(source_dir) if source_dir else SOURCE_DIR)
    if client is None:
        client = get_client()

    handler = _JsonWatchHandler(client)
    observer = Observer()
    observer.schedule(handler, path, recursive=False)
    observer.start()
    logger.info(f"👁 Watching {path} for new JSON files…")
    return observer
