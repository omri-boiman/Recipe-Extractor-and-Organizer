import os
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from typing import List, Optional, Tuple
import re
import unicodedata
import html

"""
Configuration & secrets loading
Prefer environment variables. As a fallback, if no env var is present, read an
apikey from a local file 'apikey.txt' next to this script (not committed).
"""

# Allow overrides via environment variables
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://models.github.ai/inference")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-4.1")


def _load_github_token() -> str:
    """
    Load a GitHub Models token from env or apikey.txt. Sanitizes common mistakes:
    - If multiple lines are present, tries to extract the first valid GitHub token.
    - Rejects OpenAI keys (sk-*) for this endpoint.
    """
    # 1) Environment variable takes precedence
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        # 2) Fallback to local file (ignored by git)
        apikey_path = os.path.join(os.path.dirname(__file__), "apikey.txt")
        try:
            with open(apikey_path, "r", encoding="utf-8") as f:
                token = f.read()
        except FileNotFoundError:
            token = None

    if not token:
        return ""

    raw = str(token)
    # Normalize newlines and whitespace
    compact = raw.replace("\r", "\n").strip()
    # If the string contains multiple lines or words, try to find a GitHub token pattern
    if ("\n" in compact) or (" " in compact or "\t" in compact):
        # Prefer modern github_pat_ first, then classic ghp_
        m = re.search(r"(github_pat_[A-Za-z0-9_]{50,})", compact)
        if not m:
            m = re.search(r"(ghp_[A-Za-z0-9]{20,})", compact)
        if m:
            return m.group(1)
        # Explicitly reject OpenAI-style keys which won't work here
        if re.search(r"\bsk-[A-Za-z0-9_-]+", compact):
            raise RuntimeError(
                "GITHUB_TOKEN appears to be an OpenAI key (starts with sk-). "
                "Use a GitHub token (ghp_ or github_pat_) for https://models.github.ai/inference."
            )
        # Otherwise fail clearly
        raise RuntimeError(
            "GITHUB_TOKEN contains multiple lines or invalid characters. "
            "Put a single GitHub token (ghp_... or github_pat_...) in .env or apikey.txt."
        )

    # Single value: validate format
    compact = compact.strip()
    if compact.startswith("sk-"):
        raise RuntimeError(
            "GITHUB_TOKEN appears to be an OpenAI key (starts with sk-). "
            "Use a GitHub token (ghp_ or github_pat_) for https://models.github.ai/inference."
        )
    return compact


GITHUB_TOKEN = _load_github_token()
if not GITHUB_TOKEN:
    raise RuntimeError(
        "Missing GITHUB_TOKEN. Set the environment variable or create an 'apikey.txt' "
        "file with the token (one line) next to app.py."
    )

client = ChatCompletionsClient(
    endpoint=AZURE_ENDPOINT,
    credential=AzureKeyCredential(GITHUB_TOKEN),
)

# SQLite DB path (stored next to this file)
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "recipes.db")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# ----- DATA MODELS -----
class RecipeResponse(BaseModel):
    title: str
    author: str
    source_url: str
    prep_time: Optional[int] = 0
    cook_time: Optional[int] = 0
    total_time: Optional[int] = 0
    servings: str
    ingredients: List[str]
    steps: List[str]
    image_url: Optional[str] = None

class IngredientItem(BaseModel):
    name: str
    quantity: Optional[str] = ""
    unit: Optional[str] = ""

class IngredientsSection(BaseModel):
    section: str
    items: List[str]

class StepsSection(BaseModel):
    section: str
    items: List[str]

class RecipeForUI(BaseModel):
    title: str
    author: str
    source_url: str
    prep_time: Optional[int] = 0
    cook_time: Optional[int] = 0
    total_time: Optional[int] = 0
    servings: str
    ingredients: List[IngredientsSection]
    steps: List[StepsSection]

# ----- UTILS -----
def time_to_minutes(text: str) -> int:
    if not text:
        return 0
    text = str(text)
    text = text.strip()
    # Try ISO 8601 duration: PT1H30M
    m = re.match(r"^P(?:T(?:(\d+)H)?(?:(\d+)M)?)", text.upper())
    if m:
        hours = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        return hours * 60 + mins
    # fallback to previous heuristic
    matches = re.findall(r"(\d+(?:\s*\d+/\d+)?|\d+\.\d+)\s*(hour|hr|h|minute|min|m)s?", text.lower())
    total = 0
    for amount, unit in matches:
        # handle mixed numbers like "1 1/2"
        amount = amount.strip()
        if " " in amount and "/" in amount:
            whole, frac = amount.split()
            num, den = frac.split("/")
            amount_val = int(whole) + (int(num)/int(den))
        elif "/" in amount:
            num, den = amount.split("/")
            amount_val = int(num)/int(den)
        else:
            amount_val = float(amount)
        if "hour" in unit or unit in ("h","hr"):
            total += int(amount_val * 60)
        else:
            total += int(amount_val)
    return total



def fetch_html(url: str) -> str:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        r = s.get(url, timeout=15)
        r.raise_for_status()
        # Ensure we have normalized text and unescaped HTML entities
        t = r.text
        t = html.unescape(t)
        t = unicodedata.normalize("NFKC", t)
        return t
    except Exception as e:
        raise
def extract_jsonld_recipe(soup: BeautifulSoup) -> Optional[dict]:
    for script in soup.select("script[type='application/ld+json']"):
        try:
            txt = script.string or ""
            txt = html.unescape(txt)
            obj = json.loads(txt)
            # JSON-LD may be list or dict; find recipe object
            candidates = obj if isinstance(obj, list) else [obj]
            for c in candidates:
                # If it's a graph
                if isinstance(c, dict) and "@graph" in c:
                    for g in c["@graph"]:
                        if g.get("@type","").lower() == "recipe" or "Recipe" in str(g.get("@type","")):
                            return g
                if isinstance(c, dict) and (c.get("@type","") == "Recipe" or "recipe" in str(c.get("@type","")).lower()):
                    return c
        except Exception:
            continue
    return None
    last_err: Exception | None = None
    for hdrs in headers_list:
        try:
            resp = requests.get(url, headers=hdrs, timeout=15)
            resp.raise_for_status()
            return resp.text
        except Exception as e:  # HTTPError or network error
            last_err = e
            continue

    # Final plain attempt without headers
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        last_err = e
        # Re-raise for higher-level handler
        raise

def parse_ingredient_line(line: str) -> IngredientItem:
    line = clean_text(line)
    # Remove parenthetical notes at end (retain if essential? simple approach)
    line = re.sub(r"\s*\(.*?\)\s*$", "", line)
    # match quantity like "1 1/2", "¾", "0.5", "2"
    qty_match = re.match(r"^([0-9]+(?:\s+[0-9]+/[0-9]+)?|[0-9]+/[0-9]+|[0-9]*\.[0-9]+|[¼½¾⅓⅔⅛⅜⅝⅞])\s*(.*)$", line)
    qty = ""
    unit = ""
    name = line
    if qty_match:
        qty = qty_match.group(1)
        rest = qty_match.group(2).strip()
        # first token may be unit
        parts = rest.split(None, 1)
        if parts:
            # if the first token is short and alphabetic -> unit
            if re.match(r"^[A-Za-z]{1,6}\.?$", parts[0]):
                unit = parts[0]
                name = parts[1] if len(parts) > 1 else ""
            else:
                name = rest
        else:
            name = rest
    else:
        # no qty — possibly "- salt to taste" or "salt"
        name = line
    return IngredientItem(name=name.strip(), quantity=qty.strip(), unit=unit.strip())

def clean_ingredients(raw_ingredients: List[str]) -> List[IngredientsSection]:
    """
    Organize ingredients into sections by detecting lines ending with ':'.
    Each section just stores raw strings (no quantity parsing).
        # Load environment variables from a local .env if available (for dev). In prod, use real env vars.
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
        except Exception:
            pass
    If no section is found, everything is placed under 'Main'.
    """
    sections: List[IngredientsSection] = []
    current_section = IngredientsSection(section="Main", items=[])

    for line in raw_ingredients:
        line = line.strip()
        if not line:
            continue

        # If line ends with ":", start a new section
        if line.endswith(":"):
            if current_section.items:  # save the previous section
                sections.append(current_section)
            current_section = IngredientsSection(section=line[:-1], items=[])
        else:
            current_section.items.append(line)

    # Add the last section
    if current_section.items:
        sections.append(current_section)

    return sections

def clean_steps(raw_steps: List[str]) -> List[StepsSection]:
    """
    Organize steps into sections using the same rule as ingredients:
    a line that ends with ':' starts a new section; subsequent lines belong to it.
    If no section headers are found, place all steps under 'Steps'.
    """
    sections: List[StepsSection] = []
    current_section = StepsSection(section="Steps", items=[])

    generic_labels = {"step", "steps", "instruction", "instructions", "method", "methods", "directions"}

    def normalize_step_text(t: str) -> str:
        t = t.strip()
        # Remove bullet and numbering prefixes
        t = re.sub(r"^[\-•\*]\s*", "", t)  # bullets
        t = re.sub(r"^\d+\s*[\.)]\s*", "", t)  # 1. or 1)
        # Remove 'Step 1:', 'STEP 1 -', 'Step:' etc. (case-insensitive)
        t = re.sub(r"^(?:step\s*\d*\s*[:\-\.)]?\s*)", "", t, flags=re.IGNORECASE)
        return t.strip()

    for raw in raw_steps or []:
        line = (raw or "").strip()
        if not line:
            continue

        # Section header detection: ends with ':' and isn't a generic label
        if line.endswith(":"):
            header = line[:-1].strip()
            # Ignore generic headers and plain 'Step' labels like 'Step 1:'
            if header and header.lower() not in generic_labels and not re.match(r"^step\s*\d*\s*$", header, flags=re.IGNORECASE):
                if current_section.items:
                    sections.append(current_section)
                current_section = StepsSection(section=header, items=[])
                continue
            # else fall-through, treat as a normal line after stripping prefix

        # Normalize and filter noisy lines
        norm = normalize_step_text(line)
        if not norm:
            continue
        if norm.lower() in generic_labels:
            continue

        # Avoid adding repeated identical lines consecutively
        if current_section.items and current_section.items[-1] == norm:
            continue

        current_section.items.append(norm)

    if current_section.items:
        sections.append(current_section)

    # Fallback: if nothing was captured, keep original (minus generic labels)
    total_items = sum(len(s.items) for s in sections)
    if total_items == 0 and (raw_steps or []):
        fallback = [
            (s or "").strip() for s in raw_steps
            if (s or "").strip() and (s or "").strip().lower() not in generic_labels
        ]
        if fallback:
            return [StepsSection(section="Steps", items=fallback)]

    return sections
def clean_text(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ----- RECIPE EXTRACTION -----

def heuristic_extract(soup: BeautifulSoup, url: str) -> RecipeResponse:
    # Try common selectors for title, author, ingredients, steps, servings, prep/cook time
    title = soup.select_one("h1") or soup.select_one(".recipe-title") or soup.title
    author = soup.select_one(".author") or soup.select_one(".byline")
    ingredients = [li.get_text(strip=True) for li in soup.select(".ingredient, li")]
    steps = [p.get_text(strip=True) for p in soup.select(".instruction, .step, p")]
    prep_time = soup.select_one(".prep-time")
    cook_time = soup.select_one(".cook-time")
    total_time = soup.select_one(".total-time")
    servings = soup.select_one(".servings")

    return RecipeResponse(
        title=title.get_text(strip=True) if title else "",
        author=author.get_text(strip=True) if author else "",
        source_url=url,
        prep_time=time_to_minutes(prep_time.get_text(strip=True) if prep_time else ""),
        cook_time=time_to_minutes(cook_time.get_text(strip=True) if cook_time else ""),
        total_time=time_to_minutes(total_time.get_text(strip=True) if total_time else ""),
        servings=str(servings.get_text(strip=True) if servings else ""),
        ingredients=ingredients,
        steps=steps
    )

def _normalize_ai_recipe_dict(data: dict, url: str) -> dict:
    """Ensure keys exist, normalize types, and force source_url to the request URL."""
    # Ensure keys exist
    for f in ["title", "author", "source_url", "prep_time", "cook_time", "total_time", "servings", "ingredients", "steps"]:
        if f not in data:
            data[f] = [] if f in ["ingredients", "steps"] else ""

    # Convert times
    data["prep_time"] = time_to_minutes(data.get("prep_time", ""))
    data["cook_time"] = time_to_minutes(data.get("cook_time", ""))
    data["total_time"] = time_to_minutes(data.get("total_time", ""))
    # Servings to string
    data["servings"] = str(data.get("servings", ""))
    # Always prefer the requested URL
    data["source_url"] = url or str(data.get("source_url", ""))
    # Coerce ingredients/steps lists
    if not isinstance(data.get("ingredients"), list):
        data["ingredients"] = []
    if not isinstance(data.get("steps"), list):
        data["steps"] = []
    return data


def ai_extract(text: str, url: str) -> Tuple[RecipeResponse, str]:
    system_msg = SystemMessage(content="You are a helpful assistant extracting recipe info word by word.")
    user_msg = UserMessage(content=f"Extract recipe from this text word by word:\n{text}\nReturn JSON with keys: title, author, source_url, prep_time, cook_time, total_time, servings, ingredients[], steps[]")

    response = client.complete(
        messages=[system_msg, user_msg],
        model=MODEL_NAME
    )

    # Parse AI JSON response
    content = response.choices[0].message.content
    try:
        import json
        data = json.loads(content)
    except Exception:
        data = {}

    data = _normalize_ai_recipe_dict(data, url)
    return RecipeResponse(**data), content or ""


def ai_refine_from_first(raw_ai_output: str, url: str) -> RecipeResponse:
    """
    Legacy refine: kept for compatibility but not used. Attempts to coerce raw output into JSON.
    """
    system_msg = SystemMessage(content="You are a careful formatter. Convert messy extraction into clean JSON.")
    user_msg = UserMessage(content=(
        "Given this raw assistant output about a recipe, reorganize it into strict JSON with keys: "
        "title, author, source_url, prep_time, cook_time, total_time, servings, ingredients[], steps[]. "
        "Return JSON only. If missing, leave empty.\n\n"
        f"RAW:\n{raw_ai_output}"
    ))

    response = client.complete(messages=[system_msg, user_msg], model=MODEL_NAME)
    content = response.choices[0].message.content
    try:
        import json
        data = json.loads(content)
    except Exception:
        data = {}
    data = _normalize_ai_recipe_dict(data, url)
    return RecipeResponse(**data)


def ai_refine_missing_fields(text: str, url: str, base: RecipeResponse) -> RecipeResponse:
    """Attempt to fill only missing fields with targeted prompts."""
    sys = SystemMessage(content="You are a precise extractor. Output strict JSON only, no prose.")

    def call(prompt: str) -> dict:
        resp = client.complete(messages=[sys, UserMessage(content=prompt)], model=MODEL_NAME)
        content = resp.choices[0].message.content
        try:
            import json
            return json.loads(content)
        except Exception:
            return {}

    updated = base

    # Steps
    if not (updated.steps and len(updated.steps) > 0):
        d = call(
            "Extract ONLY the steps as JSON: {\"steps\": [string, ...]}. "
            "Use one concise step per item. Return JSON only.\n\nCONTENT:\n" + text
        )
        steps = d.get("steps")
        if isinstance(steps, list) and steps:
            steps_str = [str(s).strip() for s in steps if str(s).strip()]
            updated = RecipeResponse(
                title=updated.title,
                author=updated.author,
                source_url=url,
                prep_time=updated.prep_time,
                cook_time=updated.cook_time,
                total_time=updated.total_time,
                servings=updated.servings,
                ingredients=updated.ingredients,
                steps=steps_str,
                image_url=updated.image_url,
            )

    # Ingredients
    if not (updated.ingredients and len(updated.ingredients) > 0):
        d = call(
            "Extract ONLY the ingredients as JSON: {\"ingredients\": [string, ...]}. "
            "One ingredient per item. Return JSON only.\n\nCONTENT:\n" + text
        )
        ings = d.get("ingredients")
        if isinstance(ings, list) and ings:
            ings_str = [str(s).strip() for s in ings if str(s).strip()]
            updated = RecipeResponse(
                title=updated.title,
                author=updated.author,
                source_url=url,
                prep_time=updated.prep_time,
                cook_time=updated.cook_time,
                total_time=updated.total_time,
                servings=updated.servings,
                ingredients=ings_str,
                steps=updated.steps,
                image_url=updated.image_url,
            )

    # Times
    if (not updated.prep_time) or (not updated.cook_time) or (not updated.total_time):
        d = call(
            "Extract ONLY times in minutes as JSON: {\"prep_time\": number, \"cook_time\": number, \"total_time\": number}. "
            "If unknown, use 0. Return JSON only.\n\nCONTENT:\n" + text
        )
        pt = time_to_minutes(str(d.get("prep_time", "")))
        ct = time_to_minutes(str(d.get("cook_time", "")))
        tt = time_to_minutes(str(d.get("total_time", "")))
        updated = RecipeResponse(
            title=updated.title,
            author=updated.author,
            source_url=url,
            prep_time=updated.prep_time or pt,
            cook_time=updated.cook_time or ct,
            total_time=updated.total_time or tt,
            servings=updated.servings,
            ingredients=updated.ingredients,
            steps=updated.steps,
            image_url=updated.image_url,
        )

    # Title / Author / Servings
    need_title = not (updated.title or "").strip()
    need_author = not (updated.author or "").strip()
    need_servings = not (updated.servings or "").strip()
    if need_title or need_author or need_servings:
        fields = []
        if need_title:
            fields.append("title")
        if need_author:
            fields.append("author")
        if need_servings:
            fields.append("servings")
        wanted = ", ".join(fields)
        d = call(
            f"Extract ONLY these fields as JSON: {wanted}. For 'servings' return a short string like '4' or '4 servings'. "
            "Return JSON only.\n\nCONTENT:\n" + text
        )
        title = (str(d.get("title")) if need_title and d.get("title") is not None else updated.title)
        author = (str(d.get("author")) if need_author and d.get("author") is not None else updated.author)
        servings = (str(d.get("servings")) if need_servings and d.get("servings") is not None else updated.servings)
        updated = RecipeResponse(
            title=title or "",
            author=author or "",
            source_url=url,
            prep_time=updated.prep_time,
            cook_time=updated.cook_time,
            total_time=updated.total_time,
            servings=servings or "",
            ingredients=updated.ingredients,
            steps=updated.steps,
            image_url=updated.image_url,
        )

    return updated
# ----- POST-PROCESS AI RECIPE -----
def convert_to_ui_recipe(recipe: RecipeResponse) -> RecipeForUI:
    """
    Converts RecipeResponse to RecipeForUI with structured ingredients.
    Uses a second AI call to clean ingredients.
    """
    # Use AI to clean ingredients
    cleaned_ingredients = clean_ingredients(recipe.ingredients)

    # Build steps sections similarly
    cleaned_steps = clean_steps(recipe.steps)

    return RecipeForUI(
        title=recipe.title,
        author=recipe.author,
        source_url=recipe.source_url,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        total_time=recipe.total_time,
        servings=recipe.servings,
        ingredients=cleaned_ingredients,
        steps=cleaned_steps
    )

# ----- FASTAPI APP -----
app = FastAPI()


# ----- DATABASE -----
def init_db() -> None:
    """Create the SQLite tables if they don't already exist."""
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        # Main recipes table; ingredients and steps stored as JSON text
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                author TEXT,
                source_url TEXT UNIQUE,
                prep_time INTEGER,
                cook_time INTEGER,
                total_time INTEGER,
                servings TEXT,
                ingredients_json TEXT,
                steps_json TEXT,
                image_url TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # If column didn't exist previously, add it
        try:
            cur.execute("ALTER TABLE recipes ADD COLUMN image_url TEXT")
        except sqlite3.OperationalError:
            pass
        con.commit()
    finally:
        con.close()


def save_recipe(recipe: RecipeResponse) -> int:
    """
    Insert or update a recipe. Stores ingredients as structured JSON for UI.
    """
    # Convert to UI format
    ui_recipe = convert_to_ui_recipe(recipe)

    # Ensure we have a valid unique source_url (avoid empty-string conflicts)
    source_url = (recipe.source_url or "").strip()
    if not source_url:
        import hashlib, time
        seed = f"{recipe.title}|{(recipe.steps[0] if recipe.steps else '')}|{time.time()}".encode("utf-8")
        h = hashlib.sha256(seed).hexdigest()[:16]
        source_url = f"generated:{h}"

    # Prepare JSON for DB
    ingredients_json = json.dumps([
    {"section": s.section, "items": s.items}
    for s in ui_recipe.ingredients
    ])
    steps_json = json.dumps([
        {"section": s.section, "items": s.items}
        for s in ui_recipe.steps
    ])

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO recipes (
                title, author, source_url, prep_time, cook_time, total_time,
                servings, ingredients_json, steps_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET
                title=excluded.title,
                author=excluded.author,
                prep_time=excluded.prep_time,
                cook_time=excluded.cook_time,
                total_time=excluded.total_time,
                servings=excluded.servings,
                ingredients_json=excluded.ingredients_json,
                steps_json=excluded.steps_json
        """, (
            ui_recipe.title,
            ui_recipe.author,
            source_url,
            int(ui_recipe.prep_time or 0),
            int(ui_recipe.cook_time or 0),
            int(ui_recipe.total_time or 0),
            ui_recipe.servings,
            ingredients_json,
            steps_json,
        ))
        con.commit()
        cur.execute("SELECT id FROM recipes WHERE source_url = ?", (source_url,))
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        con.close()



@app.on_event("startup")
def on_startup() -> None:
    init_db()
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# Serve the frontend: prefer Vite build (frontend/dist), else fallback to raw index.html
if os.path.isdir(DIST_DIR):
    # Serve built assets from Vite (typically under /assets)
    assets_dir = os.path.join(DIST_DIR)
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
    # Serve uploaded images
    if os.path.isdir(UPLOAD_DIR):
        app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    @app.get("/")
    def serve_built_index():
        index_path = os.path.join(DIST_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Built frontend not found. Run 'npm run build' in frontend/."}

elif os.path.isdir(FRONTEND_DIR):
    # Dev fallback: serve raw index.html and static files
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    # Serve uploaded images
    if os.path.isdir(UPLOAD_DIR):
        app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    @app.get("/")
    def root_index():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not found. Build the app or add 'frontend/index.html'."}

def _is_valid_recipe(r: RecipeResponse) -> bool:
    # Consider valid if we have a title or at least some ingredients and steps
    has_title = bool((r.title or "").strip())
    has_ings = bool(r.ingredients)
    has_steps = bool(r.steps)
    return has_title or (has_ings and has_steps)


@app.post("/extract-recipe", response_model=RecipeResponse)
def extract(url: str):
    try:
        html = fetch_html(url)
    except requests.HTTPError as e:
        status = e.response.status_code if getattr(e, "response", None) is not None else 500
        # Convert to a controlled error for the client
        raise HTTPException(status_code=502, detail=f"Failed to fetch page (HTTP {status}). The site may be blocking automated requests.")
    except Exception as e:
        raise HTTPException(status_code=502, detail="Failed to fetch page. Please try another URL.")
    soup = BeautifulSoup(html, "html.parser")

    # 1. Try AI first
    text = soup.get_text(separator="\n")
    try:
        recipe, _raw_ai = ai_extract(text, url)
        if _is_valid_recipe(recipe):
            try:
                save_recipe(recipe)
            except Exception as db_err:
                print("DB save failed:", db_err)
            return recipe
        # First AI returned but is missing fields -> targeted refine using the first AI result as base
        try:
            refined = ai_refine_missing_fields(text, url, recipe)
            if _is_valid_recipe(refined):
                try:
                    save_recipe(refined)
                except Exception as db_err:
                    print("DB save failed (refined):", db_err)
                return refined
        except Exception as e:
            print("AI refine failed:", e)
    except Exception as e:
        # If first AI call itself failed, skip refine and go straight to heuristic
        print("AI extraction failed:", e)

    # 2. Fallback to heuristic
    recipe = heuristic_extract(soup, url)
    try:
        save_recipe(recipe)
    except Exception as db_err:
        print("DB save failed:", db_err)
    return recipe


@app.get("/recipes", response_model=List[RecipeForUI])
def list_recipes():
    """Return all saved recipes in structured format for UI."""
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT title, author, source_url, prep_time, cook_time, total_time,
                   servings, ingredients_json, steps_json, image_url
            FROM recipes
            ORDER BY id DESC
            """
        )
        rows = cur.fetchall()
        out: List[RecipeForUI] = []
        for r in rows:
            title, author, source_url, prep_time, cook_time, total_time, servings, ing_json, steps_json, image_url = r
            
            # Load structured ingredients JSON
            ingredients_data = json.loads(ing_json) if ing_json else []
            ingredients_sections = [
                IngredientsSection(
                    section=s.get("section","Ingredients"),
                    items=s.get("items", [])
                )
                for s in ingredients_data
            ]
            
            # Load steps; support both legacy (list[str]) and new (list[section/items])
            steps_sections: List[StepsSection] = []
            if steps_json:
                try:
                    steps_data = json.loads(steps_json)
                except Exception:
                    steps_data = []
                if isinstance(steps_data, list):
                    if steps_data and isinstance(steps_data[0], str):
                        # Legacy string list -> single section
                        steps_sections = [StepsSection(section="Steps", items=steps_data)]
                    else:
                        # Expect list of dicts
                        for s in steps_data:
                            if isinstance(s, dict):
                                steps_sections.append(
                                    StepsSection(
                                        section=s.get("section", "Steps"),
                                        items=s.get("items", [])
                                    )
                                )
                else:
                    steps_sections = []
            else:
                steps_sections = []
            
            out.append(
                RecipeForUI(
                    title=title or "",
                    author=author or "",
                    source_url=source_url or "",
                    prep_time=int(prep_time or 0),
                    cook_time=int(cook_time or 0),
                    total_time=int(total_time or 0),
                    servings=str(servings or ""),
                    ingredients=ingredients_sections,
                    steps=steps_sections
                )
            )
        return out
    finally:
        con.close()


@app.delete("/recipes")
def delete_recipe(source_url: str):
    """Delete a recipe by its source_url. Returns number of rows deleted."""
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM recipes WHERE source_url = ?", (source_url,))
        con.commit()
        return {"deleted": cur.rowcount}
    finally:
        con.close()


@app.post("/recipes/upload-image")
def upload_recipe_image(source_url: str = Form(...), file: UploadFile = File(...)):
    """Upload an image and associate it with a recipe via source_url.
    Returns the stored image_url path.
    """
    # Basic validation
    content_type = file.content_type or ""
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    ext = allowed.get(content_type)
    if not ext:
        return {"error": f"Unsupported content type: {content_type}"}

    # Generate a safe filename based on source_url
    import hashlib
    h = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    filename = f"{h}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, filename)

    # Save file to disk
    with open(dest_path, "wb") as f:
        f.write(file.file.read())

    image_url = f"/uploads/{filename}"

    # Update DB
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("UPDATE recipes SET image_url = ? WHERE source_url = ?", (image_url, source_url))
        con.commit()
        if cur.rowcount == 0:
            return {"error": "Recipe not found for the provided source_url."}
    finally:
        con.close()

    return {"image_url": image_url}


# Q&A endpoint removed: previously /recipes/ask


@app.get("/db-health")
def db_health():
    """Quick DB health check: integrity_check, table exists, and recipe count."""
    result = {"ok": False, "db_path": DB_PATH}
    con = None
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        # Integrity check
        cur.execute("PRAGMA integrity_check;")
        integrity = cur.fetchone()
        result["integrity"] = integrity[0] if integrity else None

        # Table existence
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recipes'")
        table_exists = cur.fetchone() is not None
        result["recipes_table"] = table_exists

        # Count rows if table exists
        if table_exists:
            cur.execute("SELECT COUNT(*) FROM recipes")
            count = cur.fetchone()
            result["recipe_count"] = int(count[0]) if count else 0
        else:
            result["recipe_count"] = None

        result["ok"] = True
        return result
    except Exception as e:
        result["error"] = str(e)
        return result
    finally:
        try:
            if con:
                con.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Allow running the app with: py app.py
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
