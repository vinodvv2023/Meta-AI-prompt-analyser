"""Durable label decisions; Meilisearch is their rebuildable projection."""
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

LABEL_LOCK = RLock()
# shortcut: projection locking is per process; add cross-process coordination before using multiple API workers.
FIELDS = ("is_xx", "is_xxx")


@contextmanager
def connection():
    path = Path(os.getenv("LABEL_DB_PATH", str(Path(__file__).parent / "data" / "labels.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=30)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS labels (id TEXT PRIMARY KEY, metadata TEXT NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        yield db


def read(doc_id):
    with connection() as db:
        row = db.execute("SELECT metadata FROM labels WHERE id = ?", (doc_id,)).fetchone()
    return json.loads(row[0]) if row else None


def update(doc_id, change):
    with connection() as db:
        row = db.execute("SELECT metadata FROM labels WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return None
        metadata = json.loads(row[0])
        change(metadata)
        encoded = json.dumps(metadata, allow_nan=False)
        if encoded != row[0]:
            db.execute("UPDATE labels SET metadata = ? WHERE id = ?", (encoded, doc_id))
    return metadata


def seed(doc):
    seed_all([doc])
    return read(doc["id"])


def seed_all(documents):
    # One migration transaction avoids a disk flush for every imported prompt.
    with connection() as db:
        db.executemany("INSERT OR IGNORE INTO labels VALUES (?, ?)", (
            (doc["id"], json.dumps({
                "manual": {field: True if doc.get(field) is True else None for field in FIELDS},
                "applied": {field: doc.get(field) is True for field in FIELDS},
                "analysis": {"status": "not_analyzed"}, "projection_pending": False,
            })) for doc in documents
        ))


def save_analysis(doc_id, analysis, apply=False):
    def save(metadata):
        metadata["analysis"] = analysis
        if analysis.get("status") == "complete":
            metadata["last_successful_analysis_at"] = analysis.get("analyzed_at")
        if apply:
            for field, value in analysis.get("suggestions", {}).items():
                if type(value) is bool:
                    metadata["applied"][field] = value
            if all(type(value) is bool for value in analysis["suggestions"].values()):
                metadata["applied_signature"] = analysis["signature"]
    return update(doc_id, save)


def set_override(doc_id, field, value):
    if field not in FIELDS or (value is not None and type(value) is not bool):
        raise ValueError("Expected an XX/XXX boolean or null to resume automatic labeling")
    def save(metadata):
        metadata["manual"][field] = value
        metadata["override_updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata["projection_pending"] = True
    return update(doc_id, save)


def projection_done(doc_id):
    return update(doc_id, lambda metadata: metadata.update(projection_pending=False))


def project(doc):
    metadata = read(doc["id"])
    if not metadata:
        return doc
    for field in FIELDS:
        manual = metadata["manual"].get(field)
        doc[field] = manual if manual is not None else metadata["applied"].get(field, False)
    analysis = metadata["analysis"]
    mode = os.getenv("LAYA_MODE", "off").strip().lower()
    if mode == "off" and analysis.get("status") == "not_analyzed":
        analysis = {**analysis, "status": "disabled"}
    doc["label_analysis"] = {
        **analysis,
        "mode": mode,
        "manual_overrides": metadata["manual"],
        "projection_pending": metadata.get("projection_pending", False),
        "last_successful_analysis_at": metadata.get("last_successful_analysis_at"),
        "stale": bool(metadata.get("applied_signature") and
                      metadata["applied_signature"] != analysis.get("signature")),
    }
    return doc


def delete(doc_id):
    with connection() as db:
        db.execute("DELETE FROM labels WHERE id = ?", (doc_id,))
