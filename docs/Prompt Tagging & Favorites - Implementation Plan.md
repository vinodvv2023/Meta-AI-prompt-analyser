# Prompt Tagging, Favorites & Keyword Filter Tool — Implementation Plan

---

## Overview

This plan adds three major features to the existing Prompt Explorer:

| Feature | Description |
|---------|-------------|
| **1. Auto-detect + Custom Tags** | Automatically identify medium/style, lighting, composition, color palette, environment, and artist/reference style from every prompt. Users can also add custom tags. |
| **2. Favorites** | Star/unstar any conversation for quick access. |
| **3. Keyword Explorer Bar** | A toolbar at the top of the main content area showing all detected keywords grouped by category. Clicking a keyword filters and displays only the matching prompts. |

All data persists in Meilisearch (no new database). Favorites and custom tags are stored as document-level fields.

---

## Current State

The existing `classifier.py` already extracts **partial aspects**: `style`, `mood`, `setting`, `lighting`, `technical`, and `subject` into `image_aspects`. However:

- **Missing categories**: `composition`, `color_palette`, `artist_reference` are not extracted
- **No tag system**: Aspects are read-only, extracted during ingest, not editable by users
- **No favorites**: No concept of starred/pinned documents
- **No keyword explorer UI**: No way to browse by keyword

This plan extends the existing system rather than replacing it.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Meilisearch Index: "conversations"                              │
│                                                                  │
│  NEW FIELDS on each document:                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  "tags": ["cinematic", "golden hour", "studio", ...]     │    │
│  │  "custom_tags": ["my-collection", "client-project"]      │    │
│  │  "is_favorite": false                                     │    │
│  │  "detected_categories": {                                 │    │
│  │    "medium_style": ["photorealistic", "editorial"],       │    │
│  │    "lighting": ["golden hour", "rim light"],              │    │
│  │    "composition": ["shallow depth of field", "close-up"], │    │
│  │    "color_palette": ["warm tones", "desaturated"],        │    │
│  │    "environment": ["jungle", "studio"],                   │    │
│  │    "artist_reference": ["fashion editorial", "vintage"]   │    │
│  │  }                                                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  NEW filterable attributes:                                      │
│    is_favorite, tags (array), custom_tags (array)                │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                               │
│                                                                  │
│  NEW endpoints:                                                  │
│    PATCH /conversation/{id}/favorite   ← toggle favorite         │
│    PATCH /conversation/{id}/tags       ← add/remove tags        │
│    GET  /keywords                       ← all detected keywords │
│    GET  /favorites                      ← all favorited docs    │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React)                                                │
│                                                                  │
│  NEW components:                                                 │
│    KeywordExplorer.jsx    ← top toolbar, keyword chips by cat   │
│    TagManager.jsx         ← tag editing UI per conversation      │
│    FavoriteButton.jsx     ← star toggle button                   │
│                                                                  │
│  MODIFIED components:                                            │
│    App.jsx               ← add KeywordExplorer to layout         │
│    ConversationView.jsx  ← add TagManager, FavoriteButton        │
│    FilterBar.jsx         ← add "Favorites" filter option         │
│    TreeNav.jsx           ← show favorite star icon               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Expanded Keyword Detection (Backend)

### 1.1 New keyword dictionaries in `classifier.py`

Add six comprehensive keyword maps alongside the existing `STYLE_MAP`. The existing `style`, `mood`, `setting`, `lighting` entries will be reorganized into the new six-category system:

#### Category: `medium_style` (replaces + extends old `style`)
What artistic medium or rendering style is used.

```python
MEDIUM_STYLE_MAP = [
    "photorealistic", "hyperrealistic", "ultra-realistic", "photo", "photograph",
    "cinematic", "cinematic lighting", "editorial", "fashion editorial",
    "oil painting", "watercolor", "pencil sketch", "digital art", "concept art",
    "3d render", "3d model", "cg", "cgi", "ray tracing",
    "illustration", "storybook", "children's book", "comic", "manga", "anime",
    "surreal", "abstract", "minimalist", "vintage", "retro", "nostalgic",
    "futuristic", "cyberpunk", "steampunk", "gothic", "baroque",
    "impressionist", "expressionist", "pop art", "art deco", "art nouveau",
    "hyper-detailed", "ultra-detailed", "high-resolution", "8k", "4k",
    "fine art", "portrait photography", "lifestyle photography",
    "fashion photography", "street photography", "studio photography",
    "painterly", "graphic design", "poster", "magazine cover", "advertisement",
    "render", "rendering", "simulation", "realistic", "fantasy",
    "fairy tale", "documentary", "low poly", "isometric",
]
```

#### Category: `lighting` (extends existing)
```python
LIGHTING_MAP = [
    "golden hour", "golden light", "warm light",
    "cinematic lighting", "studio lighting", "soft lighting", "dramatic lighting",
    "natural light", "natural daylight", "diffused light",
    "rim light", "rim lighting", "backlight", "backlit", "back lighting",
    "volumetric", "volumetric light", "god rays", "light rays",
    "moonlight", "moon lit", "moonlit",
    "sunset", "sunrise", "twilight", "dusk", "dawn",
    "neon", "neon lights", "neon glow", "fluorescent",
    "ambient light", "ambient lighting", "ambient occlusion",
    "key light", "fill light", "three-point lighting",
    "chiaroscuro", "high key", "low key",
    "specular highlights", "catch light", "reflective light",
    "candle light", "firelight", "torch light",
    "overcast", "harsh light", "soft shadows", "hard shadows",
    "studio fog", "foggy", "hazy", "smoky",
    "cool light", "warm light", "color temperature",
]
```

#### Category: `composition` (NEW)
Camera angles, framing, and photographic composition techniques.

```python
COMPOSITION_MAP = [
    "shallow depth of field", "deep depth of field", "depth of field",
    "bokeh", "bokeh lights", "bokeh background",
    "close-up", "closeup", "macro", "extreme close-up",
    "wide angle", "wide angle shot", "ultra wide",
    "bird's eye", "bird's eye view", "top-down", "overhead shot", "aerial view",
    "low angle", "low angle shot", "worm's eye",
    "eye level", "straight on", "head-on",
    "portrait", "3/4 body", "full body", "half body", "waist-up",
    "rule of thirds", "centered", "symmetrical", "asymmetrical",
    "leading lines", "negative space", "positive space",
    "foreground", "background", "midground", "layered",
    "framing", "frame within frame", "dutch angle", "tilt",
    "panoramic", "panorama", "vertical composition", "horizontal composition",
    "dynamic", "static", "balanced", "off-center",
    "tight crop", "loose crop", "edge to edge", "edge-to-edge",
    "85mm", "50mm", "35mm", "24mm", "200mm", "telephoto", "wide lens",
    "fast shutter", "slow shutter", "motion blur", "motion frozen",
    "lens flare", "anamorphic", "fisheye", "tilt-shift",
]
```

#### Category: `color_palette` (NEW)
Color mood, grading, and palette descriptions.

```python
COLOR_PALETTE_MAP = [
    "monochrome", "black and white", "b&w", "grayscale", "greyscale",
    "sepia", "vintage color", "faded color", "desaturated", "undersaturated",
    "saturated", "oversaturated", "vibrant", "vivid", "bold colors",
    "muted", "muted tones", "pastel", "pastel colors", "soft colors",
    "warm tones", "warm palette", "warm color", "warm tone",
    "cool tones", "cool palette", "cool color", "cool tone",
    "earth tones", "earthy", "ochre", "amber", "terracotta",
    "neon palette", "neon colors", "electric", "fluorescent",
    "dark palette", "dark moody", "moody", "somber", "shadowy",
    "bright", "light", "airy", "high key lighting",
    "rich tones", "deep colors", "jewel tones", "gem tones",
    "complementary colors", "analogous colors", "triadic",
    "color grading", "color graded", "color corrected",
    "teal and orange", "orange and teal", "teal orange",
    "red and gold", "red gold", "crimson", "scarlet",
    "blue and purple", "violet", "indigo", "cobalt",
    "green palette", "emerald", "forest green", "sage",
    "split-color", "dichromatic", "duotone", "bicolor",
    "warm vintage", "cool vintage", "film grain",
    "golden hour color", "sunset color", "dusk color",
    "high contrast", "low contrast", "soft contrast",
]
```

#### Category: `environment` (extends existing `setting`)
Where the scene takes place.

```python
ENVIRONMENT_MAP = [
    "forest", "jungle", "woodland", "grove", "enchanted forest",
    "ocean", "sea", "beach", "coastline", "shore", "underwater", "coral reef",
    "mountain", "mountainside", "alpine", "hillside", "valley", "cliff",
    "desert", "sand dunes", "arid", "oasis",
    "city", "urban", "cityscape", "skyline", "downtown", "alley", "rooftop",
    "street", "road", "highway", "bridge", "tunnel",
    "space", "outer space", "galaxy", "nebula", "cosmic", "planetary",
    "lab", "laboratory", "clinic", "hospital",
    "palace", "castle", "temple", "church", "cathedral", "mosque",
    "garden", "botanical", "greenhouse", "park", "meadow", "field",
    "studio", "studio backdrop", "studio background", "soundstage",
    "indoor", "indoors", "outdoor", "outdoors", "interior", "exterior",
    "kitchen", "bedroom", "living room", "bathroom", "hallway",
    "cafe", "restaurant", "bar", "club", "theater",
    "sky", "clouds", "stormy sky", "clear sky", "night sky",
    "ancient ruins", "ruins", "archaeological", "historical",
    "futuristic city", "cyberpunk city", "sci-fi", "space station",
    "battlefield", "war zone", "arena", "colosseum",
    "snow", "ice", "arctic", "tundra", "frozen lake",
    "swamp", "marsh", "wetland", "river", "waterfall", "lake",
    "cave", "cavern", "underground", "mine",
    "countryside", "farmland", "ranch", "vineyard",
    "market", "bazaar", "souk", "flea market",
    "courtyard", "patio", "balcony", "terrace", "veranda",
    "launch pad", "complex", "industrial", "factory", "warehouse",
]
```

#### Category: `artist_reference` (NEW)
References to known art styles, photographers, artists, or aesthetic movements.

```python
ARTIST_REFERENCE_MAP = [
    "greg rutkowski", "artgerm", "alphonse mucha", "moebius",
    "studio ghibli", "ghibli", "miyazaki", "makoto shinkai",
    "wes anderson", " wes anderson color", "anderson palette",
    "peter lindbergh", "annie leibovitz", "steve mccurry",
    "national geographic", "nat geo",
    "fashion editorial", "vogue", "harper's bazaar", "vogue cover",
    "renaissance", "baroque", "rococo", "neoclassical",
    "art deco", "bauhaus", "brutalist", "mid-century", "mid-century modern",
    "1950s", "1960s", "1970s", "1980s", "retro", "vintage print",
    "film noir", "noir", "neo-noir",
    "dark academia", "cottagecore", "cyberpunk", "solarpunk", "dieselpunk",
    "ukiyo-e", "woodblock", "chinese ink", "sumi-e",
    "pop art", "op art", "minimalist art",
    "magic realism", "surrealism", "impressionism", "expressionism",
    "pre-raphaelite", "romanticism",
    "magazine cover", "editorial", "lookbook", "campaign",
    "album cover", "movie poster", "movie still", "film still",
    "old master", "classical painting", "oil on canvas",
    "high fashion", "haute couture", "couture",
    "luxury brand", "luxury advertisement", "advertisement",
    "pin-up", "glamour", "noir glamour",
    "fantasy art", "sci-fi art", "concept art",
    "trending on artstation", "artstation",
    "unreal engine", "octane render", "octane", "v-ray", "vray",
    "midjourney", "dall-e", "stable diffusion", "ai art",
]
```

### 1.2 New extraction function

A single `extract_detected_categories(text)` function will search all six maps against the prompt text. It returns:

```python
{
    "medium_style": ["photorealistic", "editorial fashion photography"],
    "lighting": ["golden hour", "rim light"],
    "composition": ["shallow depth of field", "low angle"],
    "color_palette": ["warm tones", "desaturated"],
    "environment": ["jungle"],
    "artist_reference": ["fashion editorial", "vogue"],
}
```

The existing `extract_aspects()` will be updated to call this new function internally. The old `STYLE_MAP` keys (`style`, `mood`, `setting`, `lighting`) will still be populated for backward compatibility, but `detected_categories` will be the new canonical field.

### 1.3 The `tags` field

```python
tags = []
for category_keywords in detected_categories.values():
    tags.extend(category_keywords)
```

All detected keywords across all categories are flattened into a single `tags` array for easy Meilisearch filtering.

---

## Part 2: Favorites System

### 2.1 Data model

Add to each Meilisearch document:
```
"is_favorite": false   (boolean)
```

### 2.2 Backend endpoint

```
PATCH /api/conversation/{id}/favorite
Body: { "is_favorite": true }
Response: updated document
```

Implementation:
1. Fetch current doc from Meilisearch
2. Toggle `is_favorite` field
3. Partial-update the document via `index.update_documents()`
4. Return the updated field

### 2.3 Meilisearch settings update

Add `is_favorite` to `filterableAttributes` so the FilterBar can filter by favorites.

### 2.4 Frontend: FavoriteButton component

A simple star icon button (unfilled = not favorite, filled gold = favorite). Calls the PATCH endpoint on click. Shows optimistic UI (instant visual toggle before server confirms).

### 2.5 FilterBar integration

Add a new filter option: `[Favorites]` with a star icon. When active, it passes `?favorite=true` to search/tree endpoints.

---

## Part 3: Tag System

### 3.1 Data model

Add to each Meilisearch document:
```
"tags": ["cinematic", "golden hour", "portrait", ...]          (auto-detected, flattened from categories)
"custom_tags": []                                                (user-added)
```

`tags` is populated at ingest time by the classifier. `custom_tags` starts empty and is user-editable.

### 3.2 Backend endpoint

```
PATCH /api/conversation/{id}/tags
Body: { "add": ["my-tag"], "remove": ["old-tag"] }
Response: updated document tags + custom_tags
```

Implementation:
1. Fetch current doc
2. Merge `add` items into `custom_tags` (no duplicates)
3. Remove `remove` items from `custom_tags`
4. Recompute `tags` = detected_categories flat + custom_tags
5. Partial-update document
6. Return new tags

### 3.3 Meilisearch settings

Add `tags` to `filterableAttributes` so the keyword explorer can filter.

### 3.4 Frontend: TagManager component

Per-conversation tag editor UI:

```
┌─ Tags ─────────────────────────────────────────────────────┐
│  [cinematic] [golden hour] [portrait] [shallow depth ×]    │
│                                                              │
│  [+ Add custom tag...        ]  [Add]                       │
└──────────────────────────────────────────────────────────────┘
```

- Auto-detected tags shown as non-removable chips (subtle border)
- Custom tags shown with an `x` remove button
- Input field + Add button for new custom tags
- Tags stored locally, synced to backend on change

---

## Part 4: Keyword Explorer Bar (Frontend)

### 4.1 Component: `KeywordExplorer.jsx`

Placed at the top of the main content area (above search results or conversation view).

```
┌─ Explore by Keyword ──────────────────────────────────────────────────────────────┐
│                                                                                   │
│  Medium/Style    [photorealistic 23] [cinematic 18] [editorial 12] [3d render 8] │
│  Lighting        [golden hour 15] [rim light 12] [studio lighting 9]              │
│  Composition     [shallow depth of field 20] [bokeh 14] [close-up 11]            │
│  Color Palette   [warm tones 16] [desaturated 10] [vibrant 7]                    │
│  Environment     [jungle 8] [studio 15] [garden 6] [outdoor 22]                  │
│  Artist/Ref      [fashion editorial 9] [vintage 7] [art deco 4]                  │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 How it works

1. On mount, fetch `GET /api/keywords` which returns all detected keywords grouped by category with document counts
2. Display keywords as clickable chips, grouped in collapsible category rows
3. When a keyword is clicked, it becomes "active" (highlighted) and the main content area filters to show only conversations containing that keyword
4. Multiple keywords can be active simultaneously (AND logic)
5. Active keywords show as a filter summary row below the explorer bar
6. Clicking an active keyword deactivates it

### 4.3 Backend: `GET /api/keywords`

Implementation:
1. Fetch all documents from Meilisearch (fields: `detected_categories`, `tags`)
2. Aggregate: for each category, count how many documents have each keyword
3. Sort each category's keywords by count (descending)
4. Return:

```json
{
    "medium_style": { "photorealistic": 23, "cinematic": 18, ... },
    "lighting": { "golden hour": 15, "rim light": 12, ... },
    "composition": { "shallow depth of field": 20, ... },
    "color_palette": { "warm tones": 16, ... },
    "environment": { "outdoor": 22, "jungle": 8, ... },
    "artist_reference": { "fashion editorial": 9, ... }
}
```

This endpoint can be cached (refreshed on re-ingest or periodically).

### 4.4 Filtering logic

When keywords are active, the search/tree endpoints receive additional filter params:

```
GET /api/search?q=&tags=cinematic,golden+hour
GET /api/tree?tags=cinematic,golden+hour
```

Backend builds Meilisearch filter:
```
tags IN ["cinematic"] AND tags IN ["golden hour"]
```

---

## Part 5: Re-ingest & Migration

### 5.1 Re-classify all existing documents

When the updated `classifier.py` with the new six-category keyword maps is deployed:

1. `POST /api/ingest` triggers a full re-ingest
2. Each document gets the new `detected_categories`, `tags`, `custom_tags`, and `is_favorite` fields
3. Existing documents that already had `image_aspects` will also get the new fields
4. `custom_tags` starts as `[]` and `is_favorite` starts as `false` for all existing docs

### 5.2 Preserving user data on re-ingest

During re-ingest, the system should:
1. Fetch existing document from Meilisearch
2. Preserve `custom_tags` and `is_favorite` from the existing doc
3. Recompute `detected_categories` and `tags` from the prompt text
4. Merge: `tags` = recomputed auto-tags + preserved `custom_tags`
5. Update the document

This requires modifying `ingestor.py` to check for existing docs before overwriting.

---

## Updated Meilisearch Index Schema

```json
{
    "id": "sha256_of_label_value",
    "source_file": "prompts.json",
    "parent_label": "Conversation file",
    "label": "Conversation with Meta AI_04-17-2026_...",
    "date": "2026-04-17",
    "turns": [...],
    "all_user_prompts": "...",
    "all_ai_responses": "...",
    "type": "image_prompt",
    "is_midjourney_style": true,
    "mj_flags": ["--stylize", "--hd", "--v", "--profile"],
    "has_video": false,
    "image_aspects": { ... },
    "llm_failed": false,

    "detected_categories": {
        "medium_style": ["photorealistic", "editorial"],
        "lighting": ["golden hour", "rim light"],
        "composition": ["shallow depth of field", "low angle"],
        "color_palette": ["warm tones", "desaturated"],
        "environment": ["jungle", "studio"],
        "artist_reference": ["fashion editorial"]
    },
    "tags": ["photorealistic", "editorial", "golden hour", ...],
    "custom_tags": ["my-collection"],
    "is_favorite": false
}
```

**Updated Meilisearch Settings:**

```python
"filterableAttributes": [
    "type",
    "is_midjourney_style",
    "llm_failed",
    "date",
    "has_video",
    "source_file",
    "is_favorite",     # NEW
    "tags",            # NEW (array)
    "custom_tags",     # NEW (array)
],
"searchableAttributes": [
    "all_user_prompts",
    "all_ai_responses",
    "label",
    "tags",            # NEW - allows searching by tag
    "custom_tags",     # NEW
],
```

---

## Files to Modify

### Backend

| File | Changes |
|------|---------|
| `classifier.py` | Add 6 new keyword maps, new `extract_detected_categories()` function, populate `detected_categories` and `tags` fields |
| `main.py` | Add `PATCH /conversation/{id}/favorite`, `PATCH /conversation/{id}/tags`, `GET /keywords`, `GET /favorites` endpoints. Update `_build_filter()` to handle `tags`, `favorite` params |
| `ingestor.py` | Update `setup_index()` filterable/searchable attributes. Update `ingest_file()` to preserve `custom_tags` and `is_favorite` on re-ingest |

### Frontend

| File | Changes |
|------|---------|
| `App.jsx` | Add `KeywordExplorer` component, manage `activeKeywords` state, pass to search/tree |
| `KeywordExplorer.jsx` | **NEW** — Category-grouped keyword chips with counts, click to filter |
| `TagManager.jsx` | **NEW** — Per-conversation tag display + custom tag add/remove |
| `FavoriteButton.jsx` | **NEW** — Star toggle button |
| `ConversationView.jsx` | Add `FavoriteButton` in header, add `TagManager` below aspects panel |
| `FilterBar.jsx` | Add "Favorites" filter option |
| `TreeNav.jsx` | Show star icon for favorited items |
| `SearchResults.jsx` | Pass `tags` filter param, show star icon on results |
| `index.css` | Styles for KeywordExplorer, TagManager, FavoriteButton |

### Launcher

| File | Changes |
|------|---------|
| None | No changes needed — existing `start.bat` works |

---

## Implementation Order

### Phase 1: Backend — Expanded classification (classifier.py)
1. Add the 6 keyword dictionaries
2. Write `extract_detected_categories(text)` function
3. Update `classify_document()` to populate `detected_categories` and `tags`
4. Keep existing `image_aspects` for backward compatibility
5. Test: run classifier against sample prompts, verify detection

### Phase 2: Backend — New endpoints (main.py)
1. Add `PATCH /conversation/{id}/favorite` endpoint
2. Add `PATCH /conversation/{id}/tags` endpoint
3. Add `GET /keywords` endpoint (with in-memory cache)
4. Add `GET /favorites` endpoint
5. Update `_build_filter()` to support `tags` and `favorite` params
6. Update existing `/search` and `/tree` to accept new params

### Phase 3: Backend — Meilisearch config (ingestor.py)
1. Update `setup_index()` with new filterable/searchable attributes
2. Modify `ingest_file()` to preserve user data on re-ingest

### Phase 4: Frontend — Favorites
1. Create `FavoriteButton.jsx` component
2. Integrate into `ConversationView.jsx` header
3. Add "Favorites" filter to `FilterBar.jsx`
4. Show star icon in `TreeNav.jsx`

### Phase 5: Frontend — Tags
1. Create `TagManager.jsx` component
2. Integrate into `ConversationView.jsx`
3. Wire up to backend PATCH endpoint

### Phase 6: Frontend — Keyword Explorer
1. Create `KeywordExplorer.jsx` component
2. Integrate into `App.jsx` layout
3. Wire keyword selection to filter state
4. Update `SearchResults.jsx` and `TreeNav.jsx` to handle tag filters
5. Add CSS styles

### Phase 7: Testing & Polish
1. Run full re-ingest against `prompts.json`
2. Verify keyword detection accuracy
3. Test favorite toggle persistence
4. Test custom tag add/remove
5. Test keyword explorer filtering
6. Verify backward compatibility (existing aspects still show)

---

## UI Layout (Updated)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🔮 Prompt Explorer [Meta AI]     [🔍 Search...          ]  Stats    │
├──────────────────────────────────────────────────────────────────────┤
│ [ALL] [Image] [Video] [Both] [Chat] [MJ] [Failed] [★ Favorites]     │
├──────────────────────────────────────────────────────────────────────┤
│ ┌─ Explore by Keyword ──────────────────────────────────────────┐    │
│ │ Medium/Style  [photorealistic 23] [cinematic 18]             │    │
│ │ Lighting      [golden hour 15] [rim light 12]                │    │
│ │ Composition   [shallow dof 20] [bokeh 14]                    │    │
│ │ Color         [warm tones 16] [desaturated 10]               │    │
│ │ Environment   [jungle 8] [studio 15]                         │    │
│ │ Artist/Ref    [editorial 9] [vintage 7]                      │    │
│ └────────────────────────────────────────────────────────────────┘    │
├──────────────┬───────────────────────────────────────────────────────┤
│ 📅 2026-04-17│  ┌─ Conversation Header ──────────────────────────┐   │
│   🖼 Unicorn │  │ label.txt  📅 2026-04-17  [Image] [MJ]  ★    │   │
│   🖼 child   │  │ [Copy image] [Copy video] [Copy all]           │   │
│   🖼 Photo.. │  ├─ Detected Aspects ───────────────────────────── │   │
│ 📅 2026-04-16│  │ Style: [photorealistic] [editorial]            │   │
│   🎬 Queen ★ │  │ Lighting: [rim light] [studio]                 │   │
│   🖼 Baller.. │  │ Composition: [shallow dof] [low angle]         │   │
│              │  ├─ Tags ──────────────────────────────────────── │   │
│              │  │ [cinematic] [golden hour] [studio ×]            │   │
│              │  │ [+ Add custom tag...          ] [Add]          │   │
│              │  ├─ Turn #0 ───────────────────────────────────── │   │
│              │  │ 🧑 You  [Image] [MJ Style]          [Copy]     │   │
│              │  │ Unicorn horse jumping, fairy tale              │   │
│              │  │ [--profile iy9axyv] [--stylize 900] [--hd]     │   │
│              │  ├─ Turn #1 ───────────────────────────────────── │   │
│              │  │ 🤖 Meta AI                            [Copy]     │   │
│              │  │ Here you go — unicorns mid-jump...             │   │
│              │  └────────────────────────────────────────────────┘   │
└──────────────┴───────────────────────────────────────────────────────┘
```

---

## Edge Cases & Considerations

| Concern | Solution |
|---------|----------|
| **Keyword count on large datasets** | Cache `/keywords` response in memory, invalidate on re-ingest. For 10K docs, aggregation takes <1s. |
| **Tag conflicts on re-ingest** | Merge strategy: auto-detected tags are always recomputed; `custom_tags` are preserved from existing doc |
| **Partial Meilisearch update** | Use `index.update_documents()` with only changed fields, not full document replacement |
| **Empty tags array filtering** | Meilisearch handles empty arrays gracefully — documents with no matching tag are excluded |
| **Keyword phrase matching** | Multi-word keywords like "shallow depth of field" are matched as exact substrings (case-insensitive) |
| **Duplicate keywords across categories** | A keyword like "cinematic" may appear in both medium_style and lighting. Both occurrences are kept; the flattened `tags` array deduplicates |
| **Favorite persistence across re-ingest** | Re-ingest fetches existing doc first, preserves `is_favorite`, then updates other fields |
| **Performance of keyword aggregation** | Single-pass aggregation over all docs on `/keywords` fetch. Cache for 5 minutes or until re-ingest. |

---

## Verification Plan

### Automated
1. Run updated `classifier.py` on 5 sample prompts — verify all 6 categories populate correctly
2. Hit `PATCH /conversation/{id}/favorite` — verify document updates
3. Hit `PATCH /conversation/{id}/tags` — verify custom tags add/remove
4. Hit `GET /keywords` — verify categories and counts
5. Hit `GET /search?tags=cinematic` — verify filtered results
6. Re-ingest — verify custom_tags and is_favorite preserved

### Manual
1. Open browser, verify Keyword Explorer bar renders with categories
2. Click a keyword chip — verify main content filters to matching conversations
3. Click multiple keywords — verify AND filtering works
4. Open a conversation, click star — verify favorite toggle
5. Check FilterBar — verify Favorites filter works
6. Add a custom tag — verify it persists after page refresh
7. Remove a custom tag — verify it disappears
8. Re-ingest — verify custom tags and favorites survive
