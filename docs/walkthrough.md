# Walkthrough - Extract Threads Prompts Button

We added support for on-demand extraction of Threads prompts through a dedicated frontend button that checks if the Threads API is live and gracefully displays a warning if it is offline.

## Changes Made

### 1. Threads Service API
- **File**: [api.py](file:///c:/Users/xtrem/Downloads/python_proj/JSON/backend/threads_service/api.py)
- **Modifications**:
  - Added a `@app.post("/export")` route that calls `_export_to_source()` and returns the total exported count.
  - Updated the `@app.on_event("startup")` handler `_start_watcher` to run `_export_to_source()` once immediately upon startup. This ensures that the local `source/threads-prompts.json` file starts fully in sync with the SQLite databases.

### 2. FastAPI Backend
- **File**: [main.py](file:///c:/Users/xtrem/Downloads/python_proj/JSON/backend/main.py)
- **Modifications**:
  - Imported `httpx` and `os`.
  - Added a `@app.post("/extract-threads")` endpoint that requests `/export` from the Threads API (on port `8002`), writes the updated JSON export file, and then immediately runs the Meilisearch `ingest_file` parser. This refreshes the search index synchronously.
  - Updated the `@app.get("/stats")` endpoint to perform a quick health check against the Threads API, returning `threads_api_live` (true/false) to the frontend.

### 3. Frontend App & State
- **File**: [App.jsx](file:///c:/Users/xtrem/Downloads/python_proj/JSON/frontend/src/App.jsx)
- **Modifications**:
  - Passed an `onRefresh` prop to `<StatsBar />` to increment `refreshTrigger` whenever extraction completes. This updates the left navigation tree (`TreeNav`) and statistics bar.

### 4. StatsBar Component (Button UI & Live Status check)
- **File**: [StatsBar.jsx](file:///c:/Users/xtrem/Downloads/python_proj/JSON/frontend/src/components/StatsBar.jsx)
- **Modifications**:
  - Checks the `threads_api_live` value returned by the backend's `/stats` call.
  - If **live**: Displays the **"Extract Threads"** button (`📥 Extract Threads`) next to the "Re-ingest" button.
  - If **offline**: Gracefully hides the button and displays a warning chip: **`⚠️ Threads API offline`** (preventing failed clicks and showing status).
  - Implemented `triggerExtractThreads` which calls `/api/extract-threads`, triggers `onRefresh` to update the parent state, and updates the local statistics.

---

## Verification

1. **Successful DB Sync**:
   - The SQLite databases contain a combined total of **180 image prompts**.
   - `threads-prompts.json` was updated from its old stale state of **74 prompts** to all **180 prompts**.
   - Meilisearch has successfully parsed and indexed all **180 prompts** under the source `threads`.
