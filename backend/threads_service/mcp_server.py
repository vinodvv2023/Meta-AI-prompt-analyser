"""
threads_mcp_server.py — MCP server that exposes Threads image prompts as MCP tools.

Fetches prompts from the Threads REST API and can ingest them into the
existing Meilisearch pipeline under the "threads" category.

Run:
    python -m threads_service.mcp_server
    # or: fastmcp run threads_service.mcp_server:mcp
"""
import json
import os
from typing import Optional

import httpx
from fastmcp import FastMCP

THREADS_API_URL = os.getenv("THREADS_API_URL", "http://localhost:8002")
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey123")
SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "source")

mcp = FastMCP(
    "threads-prompts",
    instructions=(
        "MCP server for Threads image prompts. "
        "Fetch prompts from the Threads SQLite DB via REST API, "
        "and optionally write them to the source JSON for Meilisearch ingestion."
    ),
)


def _api(path: str, params: dict | None = None) -> dict | list:
    with httpx.Client(base_url=THREADS_API_URL, timeout=10) as client:
        r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
def get_threads_stats() -> str:
    """Get statistics from the Threads prompts database (total posts, image prompts, unique users)."""
    data = _api("/stats")
    return json.dumps(data, indent=2)


@mcp.tool()
def list_threads_prompts(
    user_id: Optional[int] = None,
    prompt_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """
    List image prompts from Threads.
    Optionally filter by user_id or prompt_type ('image', 'none', 'unknown').
    Returns id, extracted_prompt, prompt_type, has_image, has_video, thread_url.
    """
    params = {"limit": limit, "offset": offset}
    if user_id is not None:
        params["user_id"] = user_id
    if prompt_type is not None:
        params["prompt_type"] = prompt_type

    rows = _api("/prompts", params=params)

    summaries = []
    for r in rows:
        summaries.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "extracted_prompt": (r.get("extracted_prompt") or "")[:300],
            "prompt_type": r.get("prompt_type"),
            "has_image": r.get("has_image"),
            "has_video": r.get("has_video"),
            "thread_url": r.get("thread_url", ""),
        })

    return json.dumps(summaries, indent=2, ensure_ascii=False)


@mcp.tool()
def get_threads_prompt(prompt_id: int) -> str:
    """Get the full details of a single Threads prompt by its ID."""
    data = _api(f"/prompts/{prompt_id}")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def get_threads_users() -> str:
    """List all unique users in the Threads database with their post counts."""
    data = _api("/users")
    return json.dumps(data, indent=2)


@mcp.tool()
def export_threads_to_source(
    prompt_type: str = "image",
    output_file: str = "threads-prompts.json",
) -> str:
    """
    Fetch all image prompts from the Threads API and write them as a JSON file
    to the source/ directory, formatted for ingestion into Meilisearch.

    The output file follows the same label_values structure used by the existing parser,
    with source='threads'. This triggers automatic re-ingestion via the file watcher.
    """
    all_rows = []
    offset = 0
    batch = 200

    while True:
        rows = _api("/prompts", params={
            "prompt_type": prompt_type,
            "limit": batch,
            "offset": offset,
        })
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch

    entries = []
    for row in all_rows:
        prompt_text = row.get("extracted_prompt") or ""
        if not prompt_text.strip():
            continue

        thread_url = row.get("thread_url", "")
        user_id = row.get("user_id", "")
        label = f"Threads_{user_id}_{row.get('id', 'unknown')}"

        entries.append({
            "label": label,
            "value": f"Thread Post\n\nYou: {prompt_text}\nThread AI: [Image generated from prompt]",
            "thread_url": thread_url,
            "user_id": user_id,
            "has_image": row.get("has_image", 0),
            "has_video": row.get("has_video", 0),
            "prompt_type": row.get("prompt_type", ""),
        })

    output = {
        "media": [],
        "label_values": [
            {
                "label": "Threads prompts",
                "dict": [
                    {
                        "label": "threads",
                        "dict": entries,
                    }
                ],
            }
        ],
    }

    source_path = os.path.join(SOURCE_DIR, output_file)
    with open(source_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return json.dumps({
        "status": "ok",
        "file": source_path,
        "entries": len(entries),
        "message": f"Wrote {len(entries)} prompts to {source_path}. File watcher will auto-ingest.",
    })


if __name__ == "__main__":
    mcp.run()
