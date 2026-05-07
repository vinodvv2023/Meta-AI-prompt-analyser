# Meta AI Prompt Explorer — Implementation Plan

A local, single-user tool to parse, classify, search, and browse Meta AI conversation exports.

---

## Overview

| Concern        | Choice                                       | Reason                            |
| -------------- | -------------------------------------------- | --------------------------------- |
| Project root   | `C:\Users\xtrem\Downloads\python_proj\JSON\` | User-specified                    |
| Source JSONs   | `JSON\source\*.json` (watched folder)        | Continuous drops                  |
| Search engine  | **Meilisearch** (local Windows binary)       | Instant, typo-tolerant, faceted   |
| Backend        | **FastAPI** (Python 3.11)                    | JSON parsing, ingestor, API proxy |
| Frontend       | **Vite + React**                             | Fast local SPA, no SSR needed     |
| No external DB | ✅ Meilisearch is the store                  | Single user, local only           |

---

## User Review Required

> [!IMPORTANT]
> The `source/` folder will be **watched continuously** using `watchdog`. Any new `.json` file dropped there will be parsed and ingested into Meilisearch automatically. Duplicate entries (same label + same conversation hash) will be de-duped by ID.

> [!WARNING]
> The real `prompts.json` is **8.8MB**. The initial ingest will parse all entries, classify each turn, and index them. This is a one-time cost. Subsequent files are incremental.

> [!NOTE]
> Meilisearch runs as a **separate local process** (Windows `.exe`). You need to start it once; the FastAPI server and React app connect to it on `http://localhost:7700`.

---

## Project Structure

```
JSON/
├── source/                  ← Drop new JSON files here (watched)
│   └── prompts.json
├── backend/
│   ├── main.py              ← FastAPI app (search proxy + ingest API)
│   ├── parser.py            ← JSON → structured turns
│   ├── classifier.py        ← image/video/convo type + MJ detection
│   ├── ingestor.py          ← Meilisearch indexing + watchdog watcher
│   ├── requirements.txt
│   └── .env                 ← MEILI_URL, MEILI_KEY
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── TreeNav.jsx       ← Left nav (date → label → turn)
│   │   │   ├── ConversationView.jsx
│   │   │   ├── TurnCard.jsx      ← Prompt + response pair
│   │   │   ├── SearchBar.jsx
│   │   │   └── FilterBar.jsx
│   │   └── hooks/
│   │       └── useSearch.js
│   ├── package.json
│   └── vite.config.js
├── meilisearch/
│   └── meilisearch.exe      ← Local binary (Windows)
└── start.bat                ← Starts Meilisearch + FastAPI + Vite in one click
```

---

## Proposed Changes

### 1. JSON Parsing (`parser.py`)

The `value` field in each entry is a raw multi-line string. Parsing rules:

- Skip entries where `value` starts with `http` → these are **media/image URLs**, stored as `type: media`
- Strip the header line `"Conversation with Meta AI\n\n\n"`
- Split remaining text into turns by detecting `You:` and `Meta AI:` as speaker markers
- Handle **multi-turn** conversations: each exchange is one `turn` object
- Extract date from label filename: `Conversation with Meta AI_04-17-2026_*.txt` → `2026-04-17`

**Turn object:**

```python
{
  "speaker": "You" | "Meta AI",
  "text": "...",
  "turn_index": 0  # position in the conversation
}
```

---

### 2. Classification (`classifier.py`)

Each **conversation** (full label entry) is classified by looking at ALL `You:` prompts in it:

#### Type Detection (per conversation)

| Type           | Rule                                                                                                                                                                    |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `image_prompt` | Any `You:` turn has MJ-style flags (`--v`, `--stylize`, `--ar`, `--hd`, `--chaos`, `--exp`, `--profile`, `--niji`) **without** video keywords                           |
| `video_prompt` | Any `You:` contains `"animate"`, `"create a video"`, `"create video"`, `"HD video"`, `"1080p"`, `"seconds video"`, OR any `Meta AI:` response confirms video generation |
| `both`         | Entry has both an image gen turn AND a video/animate follow-up (like the queen example)                                                                                 |
| `conversation` | Plain text Q&A, no image/video generation                                                                                                                               |
| `media`        | Value is a URL                                                                                                                                                          |

#### Midjourney Style Detection

`is_midjourney_style: true` if prompt contains **2 or more** of: `--v`, `--stylize`, `--ar`, `--hd`, `--chaos`, `--exp`, `--profile`, `--niji`

#### Image Prompt Aspects (extracted via keywords)

| Aspect      | Examples extracted                                                           |
| ----------- | ---------------------------------------------------------------------------- |
| `style`     | fairy tale, surreal, cinematic, cartoon, storybook, ultra-realistic, fantasy |
| `subject`   | unicorn, queen, chemistry, horse, portrait, landscape                        |
| `mood`      | dreamy, magical, dark, vibrant, enchanted, imperial                          |
| `technical` | HD, 1080p, specific flag values like `stylize 900`, `v 8.1`                  |
| `setting`   | forest, lab, palace, outdoor, indoor                                         |

#### LLM Failure Detection

`llm_failed: true` if any `Meta AI:` turn contains: `"I can't"`, `"I'm unable"`, `"sorry"`, `"cannot"`, `"I don't"`, `"against my"`, `"not able to"`

---

### 3. Meilisearch Index Schema

**Index name:** `conversations`

**One document = one conversation entry (full label/value pair)**

```json
{
  "id": "sha256_of_label_value",
  "source_file": "prompts.json",
  "parent_label": "Conversation file",
  "child_label": "Conversation with Meta AI_04-17-2026_...",
  "date": "2026-04-17",
  "turns": [
    { "speaker": "You", "text": "Unicorn horse jumping...", "turn_index": 0 },
    { "speaker": "Meta AI", "text": "Here you go...", "turn_index": 1 }
  ],
  "all_user_prompts": "Unicorn horse jumping, fairy tale...",
  "all_ai_responses": "Here you go — unicorns mid-jump...",
  "type": "image_prompt",
  "is_midjourney_style": true,
  "mj_flags": ["--stylize", "--hd", "--v", "--profile"],
  "has_video": false,
  "image_aspects": {
    "style": ["fairy tale", "dreamy"],
    "subject": ["unicorn", "horse"],
    "mood": ["magical"],
    "technical": ["stylize 900", "v 8.1", "HD"]
  },
  "llm_failed": false
}
```

**Meilisearch Settings:**

- `searchableAttributes`: `["all_user_prompts", "all_ai_responses", "child_label"]`
- `filterableAttributes`: `["type", "is_midjourney_style", "llm_failed", "date", "has_video"]`
- `sortableAttributes`: `["date"]`
- `rankingRules`: default + `date:desc`

---

### 4. FastAPI Backend (`main.py`)

Thin proxy + ingest trigger:

| Endpoint                                       | Purpose                                          |
| ---------------------------------------------- | ------------------------------------------------ |
| `GET /search?q=...&type=...&mj=...&failed=...` | Proxy to Meilisearch with filters                |
| `GET /tree`                                    | Return tree structure (dates → labels) for nav   |
| `GET /conversation/{id}`                       | Fetch full conversation by ID                    |
| `POST /ingest`                                 | Manually trigger a re-ingest of `source/` folder |
| `GET /stats`                                   | Count by type, total docs                        |

The `watchdog` file watcher runs as a background thread inside FastAPI on startup — so any new `.json` dropped into `source/` auto-ingests within seconds.

---

### 5. Frontend UI (`Vite + React`)

#### Search Bar

- Instant search: debounced 200ms → Meilisearch returns results with **highlighted snippets**
- Shows matched prompt text with keyword highlighted in yellow

#### Filter Bar (pill buttons)

```
[ALL] [🖼 Image Prompt] [🎬 Video] [💬 Conversation] [🎯 Midjourney] [❌ LLM Failed]
```

#### Left Tree Nav

```
📅 2026-04-17
  └── 🖼 Unicorn horse jumping...     ← truncated first prompt
  └── 🖼 child perspective of...
📅 2026-04-16
  └── 🎬 Royal fantasy queen...       ← video badge
```

Clicking a node loads the conversation in the right pane.

#### Conversation Detail View

For each turn pair:

```
┌─────────────────────────────────────────────┐
│ 🧑 You          [Image Prompt] [MJ Style]   │
│ Unicorn horse jumping, fairy tale           │
│ --profile iy9axyv --stylize 900 --hd --v 8.1│
├─────────────────────────────────────────────┤
│ 🤖 Meta AI                                  │
│ Here you go — unicorns mid-jump...          │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🧑 You          [Video Request]             │
│ Animate                                     │
├─────────────────────────────────────────────┤
│ 🤖 Meta AI                                  │
│ I generated and sent you an animated video  │
└─────────────────────────────────────────────┘
```

Multi-turn conversations show as a **vertical timeline** of turn cards.

#### Aspects Panel (right sidebar or expandable)

Shows detected aspects for image prompts:

- Style chips: `fairy tale` `dreamy`
- Subject chips: `unicorn` `horse`
- MJ Flags: `--stylize 900` `--v 8.1` `--hd`

---

## Files to Create

### Backend

#### [NEW] `JSON/backend/main.py`

#### [NEW] `JSON/backend/parser.py`

#### [NEW] `JSON/backend/classifier.py`

#### [NEW] `JSON/backend/ingestor.py`

#### [NEW] `JSON/backend/requirements.txt`

#### [NEW] `JSON/backend/.env`

### Frontend

#### [NEW] `JSON/frontend/` (Vite React app scaffold)

#### [NEW] `JSON/frontend/src/App.jsx`

#### [NEW] `JSON/frontend/src/components/TreeNav.jsx`

#### [NEW] `JSON/frontend/src/components/ConversationView.jsx`

#### [NEW] `JSON/frontend/src/components/TurnCard.jsx`

#### [NEW] `JSON/frontend/src/components/SearchBar.jsx`

#### [NEW] `JSON/frontend/src/components/FilterBar.jsx`

#### [NEW] `JSON/frontend/src/hooks/useSearch.js`

### Launcher

#### [NEW] `JSON/start.bat`

---

## Open Questions

> [!IMPORTANT]
> **Meilisearch binary**: I will download the Meilisearch Windows `.exe` automatically using a Python setup script. Or you can download it manually from https://github.com/meilisearch/meilisearch/releases. Do you have a preference?

> [!NOTE]
> **`turns` as nested objects**: Meilisearch doesn't support searching inside nested arrays natively. The workaround is flattening all user prompts into `all_user_prompts` (string) and all AI responses into `all_ai_responses` (string) for search, while keeping `turns` array for display. This is already reflected in the schema above.

> [!NOTE]
> **Same label, different dates (duplicate example in sample.json)**: The two identical entries for `04-16-2026_1776356941.txt` will be de-duped by content hash. Only one is stored.

---

## Verification Plan

### Automated

1. Run `parser.py` against `sample.json` → verify all 4 entries parse correctly
2. Run `classifier.py` → verify queen entry is classified as `both` (image + video)
3. Run Meilisearch + ingest → verify document count matches parsed count
4. Hit `/search?q=unicorn` → verify returns correct doc with highlight

### Manual

1. Open browser at `http://localhost:5173`
2. Verify tree nav shows dates and truncated prompts
3. Search for "queen" → verify highlighted result
4. Filter by "Video" → verify only video entries show
5. Click a conversation → verify multi-turn timeline renders correctly
