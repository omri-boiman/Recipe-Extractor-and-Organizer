import html
import json
import re
import unicodedata
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from .models import IngredientItem, IngredientsSection, StepsSection


def time_to_minutes(text: str) -> int:
    if not text:
        return 0
    text = str(text).strip()
    m = re.match(r"^P(?:T(?:(\d+)H)?(?:(\d+)M)?)", text.upper())
    if m:
        hours = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        return hours * 60 + mins
    matches = re.findall(r"(\d+(?:\s*\d+/\d+)?|\d+\.\d+)\s*(hour|hr|h|minute|min|m)s?", text.lower())
    total = 0
    for amount, unit in matches:
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
    r = s.get(url, timeout=15)
    r.raise_for_status()
    t = r.text
    t = html.unescape(t)
    t = unicodedata.normalize("NFKC", t)
    return t


def extract_jsonld_recipe(soup: BeautifulSoup) -> Optional[dict]:
    for script in soup.select("script[type='application/ld+json']"):
        try:
            txt = script.string or ""
            txt = html.unescape(txt)
            obj = json.loads(txt)
            candidates = obj if isinstance(obj, list) else [obj]
            for c in candidates:
                if isinstance(c, dict) and "@graph" in c:
                    for g in c["@graph"]:
                        if g.get("@type","" ).lower() == "recipe" or "Recipe" in str(g.get("@type","")):
                            return g
                if isinstance(c, dict) and (c.get("@type","") == "Recipe" or "recipe" in str(c.get("@type","")).lower()):
                    return c
        except Exception:
            continue
    return None


def parse_ingredient_line(line: str) -> IngredientItem:
    line = clean_text(line)
    line = re.sub(r"\s*\(.*?\)\s*$", "", line)
    qty_match = re.match(r"^([0-9]+(?:\s+[0-9]+/[0-9]+)?|[0-9]+/[0-9]+|[0-9]*\.[0-9]+|[¼½¾⅓⅔⅛⅜⅝⅞])\s*(.*)$", line)
    qty = ""
    unit = ""
    name = line
    if qty_match:
        qty = qty_match.group(1)
        rest = qty_match.group(2).strip()
        parts = rest.split(None, 1)
        if parts:
            if re.match(r"^[A-Za-z]{1,6}\.?$", parts[0]):
                unit = parts[0]
                name = parts[1] if len(parts) > 1 else ""
            else:
                name = rest
        else:
            name = rest
    else:
        name = line
    return IngredientItem(name=name.strip(), quantity=qty.strip(), unit=unit.strip())


def clean_ingredients(raw_ingredients: List[str]) -> List[IngredientsSection]:
    sections: List[IngredientsSection] = []
    current_section = IngredientsSection(section="Main", items=[])

    for line in raw_ingredients:
        line = line.strip()
        if not line:
            continue
        if line.endswith(":"):
            if current_section.items:
                sections.append(current_section)
            current_section = IngredientsSection(section=line[:-1], items=[])
        else:
            current_section.items.append(line)

    if current_section.items:
        sections.append(current_section)
    return sections


def clean_steps(raw_steps: List[str]) -> List[StepsSection]:
    sections: List[StepsSection] = []
    current_section = StepsSection(section="Steps", items=[])
    generic_labels = {"step", "steps", "instruction", "instructions", "method", "methods", "directions"}

    def normalize_step_text(t: str) -> str:
        t = t.strip()
        t = re.sub(r"^[\-•\*]\s*", "", t)
        t = re.sub(r"^\d+\s*[\.\)]\s*", "", t)
        t = re.sub(r"^(?:step\s*\d*\s*[:\-\.)]?\s*)", "", t, flags=re.IGNORECASE)
        return t.strip()

    for raw in raw_steps or []:
        line = (raw or "").strip()
        if not line:
            continue
        if line.endswith(":"):
            header = line[:-1].strip()
            if header and header.lower() not in generic_labels and not re.match(r"^step\s*\d*\s*$", header, flags=re.IGNORECASE):
                if current_section.items:
                    sections.append(current_section)
                current_section = StepsSection(section=header, items=[])
                continue
        norm = normalize_step_text(line)
        if not norm:
            continue
        if norm.lower() in generic_labels:
            continue
        if current_section.items and current_section.items[-1] == norm:
            continue
        current_section.items.append(norm)

    if current_section.items:
        sections.append(current_section)

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
