# Meta AI Prompt Analyser

A local-first web application for parsing, classifying, searching, and browsing your **Meta AI conversation exports**. Drop your exported JSON file into the `source/` folder and the app automatically ingests, classifies every conversation (image prompts, video prompts, Midjourney-style prompts, or plain chat), and makes them fully searchable with filters, keyword tagging, and favorites.

## Features

- **Automatic Ingestion** — Drop `.json` export files into `source/`; a file watcher picks them up and indexes them into Meilisearch within seconds
- **Full-Text Search** — Instant, typo-tolerant search across all user prompts and AI responses with highlighted snippets
- **Smart Classification** — Every conversation is auto-classified as `image_prompt`, `video_prompt`, `both`, `conversation`, or `media`
- **Midjourney Flag Detection** — Detects and parses `--v`, `--stylize`, `--ar`, `--profile`, `--sref`, and other MJ-style flags with their values
- **Six-Category Keyword Detection** — Automatically extracts keywords from prompts across: Medium/Style, Lighting, Composition, Color Palette, Environment, and Artist/Reference
- **Keyword Explorer** — Browse all detected keywords grouped by category with document counts; click to filter
- **Favorites** — Star/unstar any conversation for quick access; filter the tree and search by favorites
- **Custom Tags** — Add your own tags to any conversation alongside the auto-detected ones
- **Date Tree Navigation** — Left sidebar organizes conversations by date in reverse chronological order
- **LLM Failure Detection** — Flags conversations where Meta AI refused or failed to generate content
- **Multi-Turn Timeline** — View full back-and-forth conversations as a vertical timeline of turn cards

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (http://localhost:5173)                            │
│  React + Vite SPA                                           │
│  /api/* requests proxied to backend                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  FastAPI Backend (http://localhost:8000)                    │
│  - Search proxy (faceted filtering, highlighting)           │
│  - Favorites & tags CRUD                                    │
│  - Keyword aggregation                                      │
│  - File watcher (auto-ingest from source/)                  │
└──────────┬─────────────────────────────────┬───────────────┘
           │                                 │
┌──────────▼───────────┐    ┌────────────────▼───────────────┐
│  Meilisearch         │    │  source/ folder                │
│  (localhost:7700)    │    │  (watched for new .json files)  │
│  - Full-text search  │    │                                │
│  - Faceted filters   │    │  prompts.json ← your exports   │
│  - Document store    │    │                                │
└──────────────────────┘    └────────────────────────────────┘
```

### How It Works

1. **Export** your conversations from Meta AI as a JSON file
2. **Drop** the JSON file into the `source/` folder
3. The **file watcher** detects the new file and triggers ingestion
4. **Parser** (`backend/parser.py`) navigates the nested JSON structure, splits each conversation into multi-turn exchanges between `You:` and `Meta AI:`, and extracts metadata like date from the filename
5. **Classifier** (`backend/classifier.py`) analyzes each conversation's prompts to detect:
   - Type (image, video, both, chat, media)
   - Midjourney-style flags and reference codes
   - Six-category keywords (style, lighting, composition, color, environment, artist references)
   - LLM failure responses
6. **Ingestor** (`backend/ingestor.py`) indexes all classified documents into Meilisearch with preconfigured searchable/filterable attributes
7. The **React frontend** calls the FastAPI backend for search, tree navigation, keyword browsing, favorites, and tag management

## Project Structure

```
.
├── source/                     ← Drop your Meta AI JSON exports here
│   └── prompts.json
├── backend/
│   ├── main.py                 ← FastAPI app with all API endpoints
│   ├── parser.py               ← JSON export parser → structured turns
│   ├── classifier.py           ← Type detection + 6-category keyword extraction
│   ├── ingestor.py             ← Meilisearch indexing + file watcher
│   ├── .env                    ← Meilisearch URL & master key (create from .env.example)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── hooks/
│   │   │   └── useDebounce.js
│   │   └── components/
│   │       ├── SearchBar.jsx       ← Instant search with debounce
│   │       ├── FilterBar.jsx       ← Type/category filter pills
│   │       ├── TreeNav.jsx         ← Date-grouped sidebar navigation
│   │       ├── ConversationView.jsx← Full conversation detail view
│   │       ├── TurnCard.jsx        ← Single prompt/response turn
│   │       ├── SearchResults.jsx   ← Search results with highlighting
│   │       ├── StatsBar.jsx        ← Document counts + re-ingest trigger
│   │       ├── KeywordExplorer.jsx ← Category-grouped keyword chips
│   │       ├── TagManager.jsx      ← Custom tag add/remove
│   │       └── FavoriteButton.jsx  ← Star toggle
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docs/                        ← Implementation plans and design docs
├── start.bat                    ← One-click launcher (Windows)
└── .gitignore
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/search?q=...&type=...&mj=...&failed=...&tags=...` | Full-text search with faceted filters |
| `GET` | `/tree` | Date-grouped conversation list for sidebar |
| `GET` | `/conversation/{id}` | Full conversation document by ID |
| `PATCH` | `/conversation/{id}/favorite` | Toggle favorite (`{ "is_favorite": true }`) |
| `PATCH` | `/conversation/{id}/tags` | Add/remove custom tags (`{ "add": [...], "remove": [...] }`) |
| `GET` | `/keywords` | All detected keywords grouped by category with counts |
| `GET` | `/favorites` | All favorited conversations |
| `GET` | `/stats` | Document counts by type |
| `POST` | `/ingest` | Trigger manual re-ingest of `source/` folder |
| `GET` | `/health` | Health check (Meilisearch connectivity) |

## Prerequisites

- **Python 3.11+** — for the FastAPI backend
- **Node.js 18+** — for the React frontend
- **Meilisearch** — local binary (Windows) or [Meilisearch Cloud](https://meilisearch.com/cloud)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/vinodvv2023/Meta-AI-prompt-analyser.git
cd Meta-AI-prompt-analyser
```

### 2. Set Up Meilisearch

**Option A: Local binary (Windows)**

1. Download the latest Meilisearch Windows binary from [GitHub Releases](https://github.com/meilisearch/meilisearch/releases)
2. Place the `.exe` in the `meilisearch/` folder
3. Start it manually or use `start.bat`:
   ```
   meilisearch\meilisearch-enterprise-windows-amd64.exe --master-key masterKey123 --db-path "..\meili_data" --env development
   ```
   Meilisearch will be available at `http://localhost:7700`

**Option B: Meilisearch Cloud**

1. Create a free instance at [meilisearch.com/cloud](https://meilisearch.com/cloud)
2. Note your instance URL and API key
3. Update `backend/.env` with your credentials (see step 4)

**Option C: Docker**

```bash
docker run -d -p 7700:7700 -e MEILI_MASTER_KEY=masterKey123 -v $(pwd)/meili_data:/meili_data getmeili/meilisearch:latest
```

### 3. Set Up Python Backend

```bash
cd backend
python -m venv ..\.venv
..\.venv\Scripts\activate          # Windows
# source ../.venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
```

### 4. Configure Environment

Create `backend/.env` from the defaults:

```env
MEILI_URL=http://localhost:7700
MEILI_MASTER_KEY=masterKey123
```

If using Meilisearch Cloud, set `MEILI_URL` to your cloud instance URL and `MEILI_MASTER_KEY` to your API key.

### 5. Set Up Frontend

```bash
cd frontend
npm install
```

### 6. Add Your Data

Place your Meta AI JSON export file(s) in the `source/` folder. The expected format is:

```json
{
  "label_values": [
    {
      "label": "Conversation file",
      "dict": [
        {
          "label": "Conversation file",
          "dict": [
            {
              "label": "Conversation with Meta AI_04-17-2026_1776479869.txt",
              "value": "Conversation with Meta AI\n\n\nYou: your prompt here\nMeta AI: AI response here\n"
            }
          ]
        }
      ]
    }
  ]
}
```

## Running the App

### Windows (One-Click)

Double-click `start.bat` — it launches all three services in separate windows:

1. Meilisearch on `http://localhost:7700`
2. FastAPI backend on `http://localhost:8000` (API docs at `/docs`)
3. Vite dev server on `http://localhost:5173`

The browser opens automatically.

### Manual (Any OS)

Open three terminals:

**Terminal 1 — Meilisearch:**
```bash
# Windows
meilisearch\meilisearch-enterprise-windows-amd64.exe --master-key masterKey123 --db-path meili_data --env development

# macOS/Linux (via Docker)
docker run -it -p 7700:7700 -e MEILI_MASTER_KEY=masterKey123 getmeili/meilisearch:latest
```

**Terminal 2 — Backend:**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

## Updating

To pull the latest changes from the repository:

```bash
git pull origin main
```

Then update dependencies:

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

If there are changes to the classifier or parser, trigger a re-ingest to re-classify all documents:

1. Open `http://localhost:8000/docs`
2. Execute the `POST /ingest` endpoint, or
3. Click the refresh button in the Stats bar of the web UI

Custom tags and favorites are preserved across re-ingests.

## Classification Details

### Conversation Types

| Type | Criteria |
|------|----------|
| `image_prompt` | Contains image generation keywords or 2+ MJ flags |
| `video_prompt` | Contains video creation keywords in prompts or AI confirms video |
| `both` | Has both image and video indicators |
| `conversation` | Plain text Q&A, no generation intent |
| `media` | Value is a URL (image/file attachment) |

### Auto-Detected Keyword Categories

| Category | Examples |
|----------|---------|
| **Medium/Style** | photorealistic, cinematic, oil painting, anime, 3d render, fashion editorial |
| **Lighting** | golden hour, rim light, studio lighting, volumetric, moonlight, neon glow |
| **Composition** | shallow depth of field, bokeh, close-up, wide angle, rule of thirds, 85mm |
| **Color Palette** | warm tones, desaturated, teal and orange, film grain, high contrast |
| **Environment** | forest, studio, jungle, urban, underwater, palace, rooftop |
| **Artist/Reference** | greg rutkowski, studio ghibli, wes anderson, vogue, art deco, midjourney |

### Midjourney Flag Parsing

The classifier detects and parses flag-value pairs, including:
- Simple flags: `--hd`, `--chaos`
- Value flags: `--v 8.1`, `--stylize 900`, `--ar 16:9`
- Profile codes: `--profile gtd2rcz` (orphaned reference codes are auto-attached)
- Style references: `--sref 123456::789012` (orphaned numeric IDs are auto-attached)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Search Engine | [Meilisearch](https://meilisearch.com) |
| Backend | Python 3.11, FastAPI, uvicorn |
| Frontend | React 18, Vite 5 |
| File Watching | watchdog |
| Data Format | Meta AI JSON exports |

## License

This project is for personal use. Please respect Meta AI's terms of service regarding data exports.
