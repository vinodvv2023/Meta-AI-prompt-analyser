"""
parser.py — Parse Meta AI JSON export files into structured conversation documents.
"""
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


def extract_date_from_label(label: str) -> Optional[str]:
    """Extract ISO date from label like 'Conversation with Meta AI_04-17-2026_*.txt'"""
    match = re.search(r"(\d{2}-\d{2}-\d{4})", label)
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%m-%d-%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return match.group(1)
    return None


def parse_turns(text: str) -> List[Dict[str, Any]]:
    """
    Parse a multi-turn conversation text into a list of turn dicts.
    Handles arbitrary back-and-forth between 'You:' and 'Meta AI:'.
    """
    turns = []
    # Match 'You:' or 'Meta AI:' at the start of a line or start of string
    pattern = re.compile(r"(?:^|\n)(You:|Meta AI:)", re.MULTILINE)
    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        speaker_raw = match.group(1)
        speaker = "You" if speaker_raw.startswith("You") else "Meta AI"

        # Text starts after the matched speaker marker
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        turn_text = text[start:end].strip()
        if turn_text:
            turns.append({
                "speaker": speaker,
                "text": turn_text,
                "turn_index": i,
            })

    return turns


def parse_entry(
    label: str,
    value: str,
    parent_label: str,
    child_group_label: str,
    source_file: str,
) -> Optional[Dict[str, Any]]:
    """Parse a single JSON dict entry into a document ready for indexing."""
    stripped = value.strip()

    # --- Media URL entry (skip for full indexing but record it) ---
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return {
            "id": hashlib.sha256(f"{label}:{value}".encode()).hexdigest()[:16],
            "type": "media",
            "label": label,
            "parent_label": parent_label,
            "child_group_label": child_group_label,
            "source_file": source_file,
            "date": extract_date_from_label(label),
            "turns": [],
            "all_user_prompts": "",
            "all_ai_responses": "",
            "is_midjourney_style": False,
            "mj_flags": [],
            "has_video": False,
            "image_aspects": {},
            "llm_failed": False,
        }

    # --- Conversation entry ---
    # Strip the "Conversation with Meta AI\n\n\n" header
    text = re.sub(r"^Conversation with Meta AI\s*\n+", "", stripped, flags=re.MULTILINE)

    turns = parse_turns(text)
    if not turns:
        return None

    # Generate stable ID: sha256 of label + first 200 chars of value
    content_id = hashlib.sha256(f"{label}:{value[:200]}".encode()).hexdigest()[:16]

    all_user_prompts = " ".join(t["text"] for t in turns if t["speaker"] == "You")
    all_ai_responses = " ".join(t["text"] for t in turns if t["speaker"] == "Meta AI")

    return {
        "id": content_id,
        "label": label,
        "parent_label": parent_label,
        "child_group_label": child_group_label,
        "source_file": source_file,
        "date": extract_date_from_label(label),
        "turns": turns,
        "all_user_prompts": all_user_prompts,
        "all_ai_responses": all_ai_responses,
        # Filled by classifier
        "type": "conversation",
        "is_midjourney_style": False,
        "mj_flags": [],
        "has_video": False,
        "image_aspects": {},
        "llm_failed": False,
    }


def parse_json_file(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse a Meta AI JSON export file.
    Navigates: label_values[*] → dict[*] → dict[*] → {label, value}
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    # Strip trailing commas before ] or } — common in Meta AI exports
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
                doc = parse_entry(label, value, parent_label, child_group_label, source_file)
                if doc:
                    documents.append(doc)

    return documents


def parse_user_prompts_file(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse a custom user prompts JSON file (flat array format).
    Expected keys in each item: id, label, prompt, ai_response, type, date, is_favorite, is_xx, is_xxx, custom_tags
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON in {filepath}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Custom prompts file {filepath} must contain a JSON list")

    documents = []
    source_file = Path(filepath).name

    for idx, entry in enumerate(data):
        prompt_text = entry.get("prompt", "").strip()
        if not prompt_text:
            continue

        date_str = entry.get("date", "")
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        label_str = entry.get("label", "").strip() or f"User Prompt {date_str}"
        ai_response = entry.get("ai_response", "").strip()

        # Build conversation turns
        turns = [{"speaker": "You", "text": prompt_text, "turn_index": 0}]
        if ai_response:
            turns.append({"speaker": "Meta AI", "text": ai_response, "turn_index": 1})

        # Stable ID
        doc_id = entry.get("id")
        if not doc_id:
            doc_id = hashlib.sha256(f"user:{date_str}:{prompt_text[:200]}:{idx}".encode()).hexdigest()[:16]

        doc = {
            "id": doc_id,
            "label": label_str,
            "parent_label": "User Prompts",
            "child_group_label": "Custom",
            "source_file": source_file,
            "date": date_str,
            "turns": turns,
            "all_user_prompts": prompt_text,
            "all_ai_responses": ai_response,
            "type": entry.get("type", "image_prompt"),
            "is_midjourney_style": False,
            "mj_flags": [],
            "has_video": entry.get("type") == "video_prompt",
            "image_aspects": {},
            "llm_failed": False,
            "custom_tags": entry.get("custom_tags", []),
            "is_favorite": entry.get("is_favorite", False),
            "is_xx": entry.get("is_xx", False),
            "is_xxx": entry.get("is_xxx", False),
        }
        documents.append(doc)

    return documents
