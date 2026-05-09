"""
grok_parser.py -- Parse Grok JSON export files into structured conversation documents.

Grok export format:
  { "conversations": [ { "conversation": {...}, "responses": [ {"response": {...}} ] } ] }

Each response has: sender ("human" or "ASSISTANT"), message (str), model.
"""
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


def _safe_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    return str(val)


def _extract_date(iso_str: str) -> Optional[str]:
    if not iso_str:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", iso_str)
    return match.group(1) if match else None


def _parse_turns(responses: List[Dict]) -> List[Dict[str, Any]]:
    turns = []
    for i, item in enumerate(responses):
        rd = item.get("response", {})
        sender = rd.get("sender", "")
        message = _safe_str(rd.get("message", ""))

        if not message:
            continue

        speaker = "You" if sender == "human" else "Grok"
        turns.append({
            "speaker": speaker,
            "text": message.strip(),
            "turn_index": i,
            "model": rd.get("model", ""),
        })

    return turns


def parse_grok_conversation(conv: Dict, source_file: str) -> Optional[Dict[str, Any]]:
    conv_meta = conv.get("conversation", {})
    responses = conv.get("responses", [])

    turns = _parse_turns(responses)
    if not turns:
        return None

    conv_id = conv_meta.get("id", "")
    title = conv_meta.get("title", "")
    create_time = conv_meta.get("create_time", "")

    content_id = hashlib.sha256(
        f"grok:{conv_id}:{turns[0]['text'][:200]}".encode()
    ).hexdigest()[:16]

    all_user_prompts = " ".join(t["text"] for t in turns if t["speaker"] == "You")
    all_ai_responses = " ".join(t["text"] for t in turns if t["speaker"] == "Grok")

    date = _extract_date(create_time)
    if date:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            date = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return {
        "id": content_id,
        "label": title or conv_id,
        "parent_label": "",
        "child_group_label": "",
        "source_file": source_file,
        "date": date,
        "turns": turns,
        "all_user_prompts": all_user_prompts,
        "all_ai_responses": all_ai_responses,
        "type": "conversation",
        "is_midjourney_style": False,
        "mj_flags": [],
        "has_video": False,
        "image_aspects": {},
        "llm_failed": False,
    }


def parse_grok_file(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON in {filepath}: {exc}") from exc

    conversations = data.get("conversations", [])
    if not conversations:
        return []

    source_file = Path(filepath).name
    documents = []

    for conv in conversations:
        doc = parse_grok_conversation(conv, source_file)
        if doc:
            documents.append(doc)

    return documents
