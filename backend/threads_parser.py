"""
threads_parser.py — Parse Threads JSON export files into structured conversation documents.

Threads format is the same label_values structure but with "threads" as child_group_label
and thread-specific metadata (thread_url, user_id).
"""
import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional


def extract_threads_date(label: str) -> Optional[str]:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", label)
    return match.group(1) if match else None


def parse_threads_entry(
    label: str,
    value: str,
    parent_label: str,
    child_group_label: str,
    source_file: str,
    extra: Dict[str, Any] | None = None,
) -> Optional[Dict[str, Any]]:
    stripped = value.strip()
    if not stripped:
        return None

    if stripped.startswith("http://") or stripped.startswith("https://"):
        return None

    text = re.sub(r"^Thread Post\s*\n+", "", stripped, flags=re.MULTILINE)

    turns = []
    pattern = re.compile(r"(?:^|\n)(You:|Thread AI:)", re.MULTILINE)
    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        speaker_raw = match.group(1)
        speaker = "You" if speaker_raw.startswith("You") else "Thread AI"
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        turn_text = text[start:end].strip()
        if turn_text:
            turns.append({"speaker": speaker, "text": turn_text, "turn_index": i})

    if not turns:
        prompt_text = text.strip()
        if prompt_text:
            turns = [{"speaker": "You", "text": prompt_text, "turn_index": 0}]

    if not turns:
        return None

    content_id = hashlib.sha256(f"threads:{label}:{value[:200]}".encode()).hexdigest()[:16]

    all_user_prompts = " ".join(t["text"] for t in turns if t["speaker"] == "You")
    all_ai_responses = " ".join(t["text"] for t in turns if t["speaker"] != "You")

    extra = extra or {}

    return {
        "id": content_id,
        "label": label,
        "parent_label": parent_label,
        "child_group_label": child_group_label,
        "source_file": source_file,
        "date": extract_threads_date(label),
        "turns": turns,
        "all_user_prompts": all_user_prompts,
        "all_ai_responses": all_ai_responses,
        "thread_url": extra.get("thread_url", ""),
        "thread_user_id": extra.get("user_id", ""),
        "type": "conversation",
        "is_midjourney_style": False,
        "mj_flags": [],
        "has_video": bool(extra.get("has_video", 0)),
        "image_aspects": {},
        "llm_failed": False,
    }


def parse_threads_file(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON in {filepath}: {exc}") from exc

    documents = []
    source_file = Path(filepath).name

    for level1 in data.get("label_values", []):
        parent_label = level1.get("label", "")
        for level2 in level1.get("dict", []):
            child_group_label = level2.get("label", "")
            entries = level2.get("dict", [])
            if not entries:
                continue
            for entry in entries:
                label = entry.get("label", "")
                value = entry.get("value", "")
                if not value:
                    continue

                extra = {}
                for key in ("thread_url", "user_id", "has_image", "has_video", "prompt_type"):
                    if key in entry:
                        extra[key] = entry[key]

                doc = parse_threads_entry(
                    label, value, parent_label, child_group_label, source_file, extra
                )
                if doc:
                    documents.append(doc)

    return documents
