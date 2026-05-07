"""
classifier.py — Classify parsed conversation documents.

Types:
  image_prompt  → has MJ-style flags or image generation intent, no video
  video_prompt  → has explicit video creation intent
  both          → image + video in same conversation (e.g. "Create portrait...Create video")
  conversation  → plain text, no generation intent
  media         → raw URL entry (images/files)

Also detects:
  - Midjourney-style flag usage (--v, --stylize, etc.)
  - LLM failure responses
  - Image aspects: style, mood, setting, lighting, subject, technical specs
"""
import re
from typing import Dict, Any, List

# ─── Midjourney-style flags ────────────────────────────────────────────────
MJ_FLAGS = [
    "--v", "--stylize", "--ar", "--hd", "--chaos", "--exp",
    "--profile", "--niji", "--iw", "--q", "--seed", "--weird",
    "--tile", "--stop", "--no", "--c", "--sref", "--cref",
]

# ─── Video intent keywords (in prompts) ────────────────────────────────────
VIDEO_PROMPT_KEYWORDS = [
    "animate", "animation", "create a video", "create video",
    "make a video", "make video", "generate a video", "1080p",
    "seconds video", "hd video", "animated video", "video of",
    "turn this into a video", "turn into a video",
]

# ─── Video confirmation in AI responses ────────────────────────────────────
VIDEO_AI_CONFIRMS = [
    "animated video", "generated and sent", "animated her",
    "animated into", "here is your video", "here's your video",
    "10-second", "second video", "sent you an animated",
]

# ─── Image generation intent keywords ─────────────────────────────────────
IMAGE_KEYWORDS = [
    "portrait", "image", "photo", "picture", "illustration",
    "draw", "generate", "create", "show me", "make", "design",
    "render", "painting", "artwork", "wallpaper",
]

# ─── LLM failure indicators ────────────────────────────────────────────────
FAILURE_KEYWORDS = [
    "i can't", "i'm unable", "sorry, i", "cannot generate",
    "i don't", "against my", "not able to", "i am unable",
    "i apologize", "i won't", "will not generate",
    "not appropriate", "violates", "that request",
]

# ─── Aspect keyword maps (legacy — kept for backward compat) ──────────────
STYLE_MAP: Dict[str, List[str]] = {
    "style": [
        "fairy tale", "surreal", "cinematic", "cartoon", "storybook",
        "ultra-realistic", "fantasy", "anime", "watercolor", "oil painting",
        "sketch", "realistic", "abstract", "minimalist", "vintage", "retro",
        "futuristic", "cyberpunk", "steampunk", "gothic", "impressionist",
        "photorealistic", "hyperrealistic", "painterly", "digital art",
        "concept art", "children's book", "comic", "3d render",
    ],
    "mood": [
        "dreamy", "magical", "dark", "vibrant", "enchanted", "imperial",
        "epic", "peaceful", "dramatic", "ethereal", "mysterious",
        "romantic", "melancholic", "cheerful", "gloomy", "serene",
        "majestic", "whimsical", "eerie", "joyful", "intense",
    ],
    "setting": [
        "forest", "lab", "palace", "outdoor", "indoor", "space",
        "ocean", "mountain", "city", "desert", "underwater", "sky",
        "castle", "jungle", "street", "studio", "garden", "battlefield",
        "ancient", "futuristic city",
    ],
    "lighting": [
        "golden hour", "cinematic lighting", "soft light",
        "dramatic lighting", "moonlight", "sunset", "sunrise",
        "neon lights", "natural light", "studio lighting",
        "rim light", "backlight", "volumetric", "god rays",
    ],
}

# ─── Expanded six-category keyword maps ───────────────────────────────────

MEDIUM_STYLE_MAP: List[str] = [
    "photorealistic", "hyperrealistic", "hyper-realistic", "ultra-realistic",
    "photo", "photograph", "photography", "photographic",
    "cinematic", "editorial", "fashion editorial", "luxury fashion editorial",
    "oil painting", "watercolor", "watercolour", "pencil sketch", "ink drawing",
    "digital art", "concept art", "digital painting",
    "3d render", "3d model", "cg", "cgi", "ray tracing", "octane render", "octane",
    "v-ray", "vray", "unreal engine",
    "illustration", "storybook illustration", "storybook", "children's book",
    "comic", "manga", "anime", "graphic novel",
    "surreal", "surrealism", "abstract", "abstract art", "minimalist", "minimalism",
    "vintage", "retro", "nostalgic", "vintage print", "vintage aesthetic",
    "futuristic", "cyberpunk", "steampunk", "dieselpunk", "solarpunk",
    "gothic", "baroque", "rococo", "neoclassical",
    "impressionist", "impressionism", "expressionist", "expressionism",
    "pop art", "op art", "art deco", "art nouveau", "bauhaus", "brutalist",
    "fairy tale", "fantasy", "fantasy art", "dark fantasy", "high fantasy",
    "documentary", "documentary style", "photojournalism",
    "low poly", "isometric", "pixel art", "voxel",
    "fine art", "portrait photography", "lifestyle photography",
    "fashion photography", "street photography", "studio photography",
    "painterly", "painterly realism", "graphic design", "poster", "magazine cover",
    "magazine layout", "advertisement", "luxury advertisement",
    "render", "rendering", "simulation", "realistic",
    "portrait", "caricature", "collage", "mixed media",
    "glamour", "pin-up", "boudoir",
    "ultra-detailed", "hyper-detailed", "highly detailed", "intricate detail",
    "high-resolution", "high resolution", "8k", "4k", "ultra hd",
]

LIGHTING_MAP: List[str] = [
    "golden hour", "golden light", "golden hour lighting",
    "cinematic lighting", "studio lighting", "soft lighting", "dramatic lighting",
    "natural light", "natural daylight", "diffused light", "soft diffused",
    "rim light", "rim lighting", "backlight", "backlit", "back lighting",
    "volumetric", "volumetric light", "god rays", "light rays", "crepuscular rays",
    "moonlight", "moon lit", "moonlit",
    "sunset", "sunrise", "twilight", "dusk", "dawn",
    "neon", "neon lights", "neon glow", "neon lighting", "fluorescent",
    "ambient light", "ambient lighting", "ambient occlusion",
    "key light", "fill light", "three-point lighting",
    "chiaroscuro", "high key", "low key", "low-key", "high-key",
    "specular highlights", "specular", "catch light", "reflective light",
    "candle light", "candlelight", "firelight", "torch light",
    "overcast", "harsh light", "soft shadows", "hard shadows", "deep shadows",
    "studio fog", "foggy", "hazy", "smoky", "misty",
    "cool light", "warm light", "color temperature",
    "rim highlights", "edge lighting", "contour lighting",
    "silhouette lighting", "halo lighting", "bloom",
    "environment lighting", "image-based lighting", "hdr lighting",
]

COMPOSITION_MAP: List[str] = [
    "shallow depth of field", "deep depth of field", "depth of field",
    "bokeh", "bokeh lights", "bokeh background", "bokeh effect",
    "close-up", "closeup", "macro", "extreme close-up",
    "wide angle", "wide angle shot", "ultra wide", "ultrawide",
    "bird's eye", "bird's eye view", "top-down", "overhead shot", "aerial view",
    "low angle", "low angle shot", "worm's eye",
    "eye level", "straight on", "head-on", "frontal",
    "portrait", "3/4 body", "full body", "half body", "waist-up",
    "rule of thirds", "centered", "symmetrical", "symmetry", "asymmetrical",
    "leading lines", "negative space", "positive space", "dynamic negative space",
    "foreground", "background", "midground", "layered",
    "framing", "frame within frame", "dutch angle", "tilt",
    "panoramic", "panorama", "vertical composition", "horizontal composition",
    "dynamic composition", "balanced composition", "off-center",
    "tight crop", "loose crop", "edge to edge", "edge-to-edge",
    "85mm", "50mm", "35mm", "24mm", "200mm", "telephoto", "wide lens",
    "fast shutter", "slow shutter", "motion blur", "motion frozen", "motion-freeze",
    "lens flare", "anamorphic", "fisheye", "tilt-shift",
    "cinematic composition", "editorial composition",
    "flat lay", "top-down flat", "overhead flat",
    "depth and dimension", "sense of depth", "3d perspective",
]

COLOR_PALETTE_MAP: List[str] = [
    "monochrome", "black and white", "b&w", "grayscale", "greyscale",
    "sepia", "vintage color", "faded color", "desaturated", "undersaturated",
    "saturated", "oversaturated", "vibrant", "vivid", "bold colors",
    "muted", "muted tones", "pastel", "pastel colors", "soft colors",
    "warm tones", "warm palette", "warm color", "warm tone", "warm color grading",
    "cool tones", "cool palette", "cool color", "cool tone", "cool color grading",
    "earth tones", "earthy", "ochre", "amber", "terracotta",
    "neon palette", "neon colors", "electric colors", "fluorescent colors",
    "dark palette", "dark moody", "moody", "somber", "shadowy",
    "bright", "light and airy", "airy", "high key",
    "rich tones", "deep colors", "jewel tones", "gem tones",
    "complementary colors", "analogous colors", "triadic",
    "color grading", "color graded", "color corrected",
    "teal and orange", "orange and teal", "teal orange", "teal-and-orange",
    "red and gold", "red gold", "crimson", "scarlet",
    "blue and purple", "violet", "indigo", "cobalt",
    "green palette", "emerald", "forest green", "sage",
    "split-color", "dichromatic", "duotone", "bicolor", "split-color theme",
    "warm vintage", "cool vintage", "film grain",
    "golden hour color", "sunset color", "dusk color",
    "high contrast", "low contrast", "soft contrast",
    "subtle desaturation", "slight desaturation",
    "rich warm tones", "earthy ochre", "ochre and amber",
    "cool-toned", "warm-toned", "cool green", "cool-toned green",
]

ENVIRONMENT_MAP: List[str] = [
    "forest", "jungle", "woodland", "grove", "enchanted forest", "tropical jungle",
    "ocean", "sea", "beach", "coastline", "shore", "underwater", "coral reef",
    "mountain", "mountainside", "alpine", "hillside", "valley", "cliff",
    "desert", "sand dunes", "arid", "oasis",
    "city", "urban", "cityscape", "skyline", "downtown", "alley", "alleyway", "rooftop",
    "street", "road", "highway", "bridge", "tunnel",
    "space", "outer space", "galaxy", "nebula", "cosmic", "planetary",
    "lab", "laboratory", "clinic", "hospital",
    "palace", "castle", "temple", "church", "cathedral", "mosque",
    "garden", "botanical", "greenhouse", "park", "meadow", "field", "botanical garden",
    "studio", "studio backdrop", "studio background", "soundstage", "studio setting",
    "indoor", "indoors", "outdoor", "outdoors", "interior", "exterior",
    "kitchen", "bedroom", "living room", "bathroom", "hallway",
    "cafe", "restaurant", "bar", "club", "theater",
    "sky", "clouds", "stormy sky", "clear sky", "night sky", "starry sky",
    "ancient ruins", "ruins", "archaeological", "historical",
    "futuristic city", "cyberpunk city", "sci-fi", "sci-fi city", "space station",
    "battlefield", "war zone", "arena", "colosseum",
    "snow", "ice", "arctic", "tundra", "frozen lake", "snowy",
    "swamp", "marsh", "wetland", "river", "waterfall", "lake", "riverbank",
    "cave", "cavern", "underground", "mine",
    "countryside", "farmland", "ranch", "vineyard",
    "market", "bazaar", "souk", "flea market",
    "courtyard", "patio", "balcony", "terrace", "veranda",
    "launch pad", "launch complex", "industrial", "factory", "warehouse",
    "reflective water", "shallow water", "wading", "lakeside",
    "stone wall", "brick wall", "wall backdrop", "seamless backdrop",
    "carved stone", "stone pillars", "hanging bells", "temple courtyard",
]

ARTIST_REFERENCE_MAP: List[str] = [
    "greg rutkowski", "artgerm", "alphonse mucha", "moebius",
    "studio ghibli", "ghibli", "miyazaki", "makoto shinkai",
    "wes anderson", "anderson color", "anderson palette", "wes anderson color",
    "peter lindbergh", "annie leibovitz", "steve mccurry",
    "national geographic", "nat geo",
    "fashion editorial", "vogue", "harper's bazaar", "vogue cover",
    "renaissance", "baroque", "rococo", "neoclassical",
    "art deco", "art deco influence", "bauhaus", "brutalist", "mid-century",
    "mid-century modern", "1950s", "1960s", "1970s", "1980s",
    "retro", "vintage print", "vintage aesthetic", "retro aesthetic",
    "film noir", "noir", "neo-noir",
    "dark academia", "cottagecore", "cyberpunk", "solarpunk", "dieselpunk",
    "ukiyo-e", "woodblock", "chinese ink", "sumi-e",
    "pop art", "op art", "minimalist art",
    "magic realism", "surrealism", "impressionism", "expressionism",
    "pre-raphaelite", "romanticism", "romanticism",
    "magazine cover", "editorial", "lookbook", "campaign",
    "album cover", "movie poster", "movie still", "film still",
    "old master", "classical painting", "oil on canvas",
    "high fashion", "haute couture", "couture",
    "luxury brand", "luxury advertisement", "luxury print advertising", "advertisement",
    "pin-up", "glamour", "noir glamour",
    "fantasy art", "sci-fi art", "concept art",
    "trending on artstation", "artstation",
    "unreal engine", "octane render", "octane", "v-ray", "vray",
    "midjourney", "dall-e", "stable diffusion", "ai art",
    "fashion magazine", "editorial fashion", "editorial magazine",
    "retro editorial", "vintage editorial",
    "photojournalism", "street photography", "documentary photography",
]

ALL_CATEGORY_MAPS: Dict[str, List[str]] = {
    "medium_style": MEDIUM_STYLE_MAP,
    "lighting": LIGHTING_MAP,
    "composition": COMPOSITION_MAP,
    "color_palette": COLOR_PALETTE_MAP,
    "environment": ENVIRONMENT_MAP,
    "artist_reference": ARTIST_REFERENCE_MAP,
}


# Short alphanumeric codes that look like MJ reference codes (not English words)
_COMMON_EN = {
    # Prepositions, conjunctions, articles
    'about','after','again','before','being','could','other','their','there',
    'these','think','using','where','which','would',
    # Nouns commonly in prompts
    'image','photo','video','style','anime','model','child','woman','forest',
    'space','light','color','black','white','scene','ocean','night','dream',
    'queen','fairy','magic','water','earth','green','brown','stone','steel',
    'ghost','storm','blade','solar','micro','hyper','super','under','inner',
    # Adjectives
    'ultra','sharp','clean','clear','glass','metal','laser','bloom','swift',
    'neon','dark','gold','rich','warm','cool','soft','hard','deep','royal',
    'young','cyber','toxic','chaos','astro','lunar','glow','pulse','bloom',
    # Verbs
    'using','being','after','other','create','render','design','imagine',
    'facing','camera','panel','heads','young','woman','wearing','sitting',
    'standing','looking','holding','walking','running','flying','floating',
    # Scientific / organic-style words that look like codes
    'organic','chemistry','ancient','photon','carbon','silicon','neural',
    'cosmic','plasma','static','energy','matter','quantum','photon','alpha',
    'delta','gamma','sigma','omega','theta',
    # Common adjectives that pass the regex
    'portrait','render','rustic','modern','future','nature','urban','color',
    'jungle','castle','street','studio','garden','battle','palace','indoor',
    'disco','retro','around',
    # UI / tech / context words that appear in prompts
    'display','panels','camera','surround','heads','screen','frame','scene',
    'vision','window','hologram','digital','sphere','circle','spiral','prism',
    'shadow','silver','golden','copper','bronze','chrome','atomic','plasma',
    'matrix','galaxy','nebula','particle','crystal','mirror','tunnel','portal',
}


def _orphaned_tokens(pre_flag_text: str):
    """Return (numeric_ids, alpha_codes) found before first --flag."""
    nums  = re.findall(r'\b(\d{6,}(?:::\d+)?)\b', pre_flag_text)

    # Alpha codes: words that look like MJ reference codes.
    # Heuristic: contains a digit  (e.g. gtd2rcz)
    #         OR is 5–10 chars with very few vowels — hash-like consonant cluster
    #            (e.g. igusadc: 7 chars, only 2 vowels → consonant ratio 5/7 ≈ 0.71)
    def _is_mj_code(w: str) -> bool:
        if w in _COMMON_EN:
            return False
        if re.search(r'\d', w):           # has a digit → always a code
            return True
        vowels = sum(1 for c in w if c in 'aeiou')
        return len(w) >= 5 and vowels <= 2  # very few vowels = hash-like

    codes = [
        m for m in re.findall(r'\b([a-z][a-z0-9]{4,9})\b', pre_flag_text.lower())
        if _is_mj_code(m)
    ]
    return nums, codes


def detect_mj_flags(text: str) -> List[str]:
    lower = text.lower()
    return [flag for flag in MJ_FLAGS if flag in lower]


def extract_mj_flags_with_values(text: str) -> List[str]:
    """
    Parse --flag [value] pairs from a MidJourney prompt string.
    Handles:
      --sref  → multiple space-separated values until next --flag
      --profile / --style → one word value (alphanumeric code)
      all other flags → optional single numeric value
    Returns list of strings like ['--v 8.1', '--profile gtd2rcz', '--sref 123 456']
    """
    # Locate first flag
    first_flag = re.search(r'--[a-z]', text, re.I)
    pre_flag  = text[:first_flag.start()].strip() if first_flag else text
    flags_str = text[first_flag.start():].strip() if first_flag else ''

    orphan_nums, orphan_codes = _orphaned_tokens(pre_flag)

    # Parse flags
    parsed = []  # list of [flag_name, value_or_empty]
    # --sref takes multiple values; others take at most one non-flag word
    for m in re.finditer(
        r'(--sref)((?:\s+(?!--\w)\S+)+)|(--[\w-]+)((?:\s+(?!--\w)\S+)?)',
        flags_str
    ):
        if m.group(1):  # --sref
            parsed.append(['--sref', m.group(2).strip()])
        else:
            parsed.append([m.group(3), m.group(4).strip() if m.group(4) else ''])

    # Attach orphaned values
    profile = next((p for p in parsed if p[0] == '--profile' and not p[1]), None)
    if profile and orphan_codes:
        profile[1] = orphan_codes[0]

    sref = next((p for p in parsed if p[0] == '--sref'), None)
    if sref and orphan_nums:
        sref[1] = (sref[1] + ' ' + ' '.join(orphan_nums)).strip()
    elif not sref and len(orphan_nums) >= 2:
        parsed.insert(0, ['--sref', ' '.join(orphan_nums)])

    return [f"{p[0]} {p[1]}".strip() for p in parsed]


def detect_video_intent(user_prompts: str, ai_responses: str) -> bool:
    combined = (user_prompts + " " + ai_responses).lower()
    return (
        any(kw in combined for kw in VIDEO_PROMPT_KEYWORDS)
        or any(kw in ai_responses.lower() for kw in VIDEO_AI_CONFIRMS)
    )


def detect_image_intent(user_prompts: str, mj_flags: List[str]) -> bool:
    lower = user_prompts.lower()
    has_img_kw = any(kw in lower for kw in IMAGE_KEYWORDS)
    has_mj = len(mj_flags) > 0
    return has_img_kw or has_mj


def extract_aspects(text: str) -> Dict[str, List[str]]:
    text_lower = text.lower()
    aspects: Dict[str, List[str]] = {}

    for category, keywords in STYLE_MAP.items():
        found = [kw for kw in keywords if kw in text_lower]
        if found:
            aspects[category] = found

    # Technical specs: use the full flag parser so profile codes & sref IDs appear correctly
    technical: List[str] = []
    if '--' in text:
        full_flags = extract_mj_flags_with_values(text)
        technical.extend(full_flags)
    if not technical:
        # Fallback to simple number pattern
        tech_matches = re.findall(r"--(\w+)\s+([\d.]+)", text)
        technical.extend(f"{flag} {val}" for flag, val in tech_matches)
    if "--hd" in text_lower and not any('hd' in t.lower() for t in technical):
        technical.append("HD")
    if "1080p" in text_lower and "1080p" not in technical:
        technical.append("1080p")
    if "4k" in text_lower and "4K" not in technical:
        technical.append("4K")
    if technical:
        aspects["technical"] = technical

    # Simple subject extraction
    subject_patterns = [
        r"portrait of (?:a |an |the )?([a-z][a-z\s]{2,40}?)(?=\s+(?:inspired|wearing|with|in|who|\.|\,))",
        r"(?:of|showing|featuring|depicting) (?:a |an |the )?([a-z][a-z\s]{2,40}?)(?=\s+(?:jump|run|fly|stand|sit|float|\.|\,))",
        r"(?:^|\n)(?:a |an |the )([a-z][a-z\s]{2,30}?)(?=\s+(?:in|with|on|at|under|over|jump|run))",
    ]
    subjects: List[str] = []
    for pattern in subject_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            s = m.group(1).strip()
            if 3 <= len(s) <= 50:
                subjects.append(s)
    if subjects:
        aspects["subject"] = list(dict.fromkeys(subjects))[:5]

    return aspects


def extract_detected_categories(text: str) -> Dict[str, List[str]]:
    """Extract keywords from all six categories against the prompt text."""
    text_lower = text.lower()
    categories: Dict[str, List[str]] = {}

    for category, keywords in ALL_CATEGORY_MAPS.items():
        found = [kw for kw in keywords if kw in text_lower]
        if found:
            categories[category] = found

    return categories


def extract_detected_categories_with_mj(text: str, mj_flags: List[str]) -> Dict[str, List[str]]:
    """Like extract_detected_categories but also adds a midjourney category for detected flags."""
    categories = extract_detected_categories(text)

    if mj_flags:
        categories["midjourney"] = mj_flags

    return categories


def flatten_categories(categories: Dict[str, List[str]]) -> List[str]:
    """Flatten category map into a deduplicated tags list."""
    seen = set()
    tags = []
    for kw_list in categories.values():
        for kw in kw_list:
            if kw not in seen:
                seen.add(kw)
                tags.append(kw)
    return tags


def classify_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Add classification fields to a parsed document in-place."""
    if doc.get("type") == "media":
        doc.setdefault("detected_categories", {})
        doc.setdefault("tags", [])
        doc.setdefault("custom_tags", [])
        doc.setdefault("is_favorite", False)
        return doc

    user_prompts = doc.get("all_user_prompts", "")
    ai_responses = doc.get("all_ai_responses", "")

    mj_flags = detect_mj_flags(user_prompts)
    is_mj = len(mj_flags) >= 2

    has_video = detect_video_intent(user_prompts, ai_responses)
    has_image = detect_image_intent(user_prompts, mj_flags)

    if has_image and has_video:
        conv_type = "both"
    elif has_video:
        conv_type = "video_prompt"
    elif has_image:
        conv_type = "image_prompt"
    else:
        conv_type = "conversation"

    llm_failed = any(kw in ai_responses.lower() for kw in FAILURE_KEYWORDS)

    aspects: Dict[str, List[str]] = {}
    detected_categories: Dict[str, List[str]] = {}
    tags: List[str] = []

    if conv_type in ("image_prompt", "video_prompt", "both"):
        aspects = extract_aspects(user_prompts)
        detected_categories = extract_detected_categories_with_mj(user_prompts, mj_flags)
        auto_tags = flatten_categories(detected_categories)
        custom_tags = doc.get("custom_tags", [])
        tags = auto_tags + [t for t in custom_tags if t not in auto_tags]

    doc.update({
        "type": conv_type,
        "is_midjourney_style": is_mj,
        "mj_flags": mj_flags,
        "has_video": has_video,
        "image_aspects": aspects,
        "llm_failed": llm_failed,
        "detected_categories": detected_categories,
        "tags": tags,
        "custom_tags": doc.get("custom_tags", []),
        "is_favorite": doc.get("is_favorite", False),
    })

    return doc
