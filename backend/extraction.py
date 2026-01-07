from typing import Tuple, List
from bs4 import BeautifulSoup
from azure.ai.inference.models import SystemMessage, UserMessage
from .config import client, MODEL_NAME
from .models import RecipeResponse, RecipeForUI
from .utils import time_to_minutes, clean_ingredients, clean_steps


def heuristic_extract(soup: BeautifulSoup, url: str) -> RecipeResponse:
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
        steps=steps,
    )


def _normalize_ai_recipe_dict(data: dict, url: str) -> dict:
    for f in ["title", "author", "source_url", "prep_time", "cook_time", "total_time", "servings", "ingredients", "steps"]:
        if f not in data:
            data[f] = [] if f in ["ingredients", "steps"] else ""
    data["prep_time"] = time_to_minutes(data.get("prep_time", ""))
    data["cook_time"] = time_to_minutes(data.get("cook_time", ""))
    data["total_time"] = time_to_minutes(data.get("total_time", ""))
    data["servings"] = str(data.get("servings", ""))
    data["source_url"] = url or str(data.get("source_url", ""))
    if not isinstance(data.get("ingredients"), list):
        data["ingredients"] = []
    if not isinstance(data.get("steps"), list):
        data["steps"] = []
    return data


def ai_extract(text: str, url: str) -> Tuple[RecipeResponse, str]:
    system_msg = SystemMessage(content="You are a helpful assistant extracting recipe info word by word.")
    user_msg = UserMessage(content=f"Extract recipe from this text word by word:\n{text}\nReturn JSON with keys: title, author, source_url, prep_time, cook_time, total_time, servings, ingredients[], steps[]")

    response = client.complete(messages=[system_msg, user_msg], model=MODEL_NAME)
    content = response.choices[0].message.content
    try:
        import json
        data = json.loads(content)
    except Exception:
        data = {}
    data = _normalize_ai_recipe_dict(data, url)
    return RecipeResponse(**data), content or ""


def ai_refine_from_first(raw_ai_output: str, url: str) -> RecipeResponse:
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
    sys_msg = SystemMessage(content="You are a precise extractor. Output strict JSON only, no prose.")

    def call(prompt: str) -> dict:
        resp = client.complete(messages=[sys_msg, UserMessage(content=prompt)], model=MODEL_NAME)
        content = resp.choices[0].message.content
        try:
            import json
            return json.loads(content)
        except Exception:
            return {}

    updated = base

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

    if (not updated.prep_time) or (not updated.cook_time) or (not updated.total_time):
        d = call(
            "Extract ONLY times in minutes as JSON: {\"prep_time\": number, \"cook_time\": number, \"total_time\": number}. "
            "If unknown, use 0. Return JSON only.\n\nCONTENT:\n" + text
        )
        from .utils import time_to_minutes as t2m
        pt = t2m(str(d.get("prep_time", "")))
        ct = t2m(str(d.get("cook_time", "")))
        tt = t2m(str(d.get("total_time", "")))
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


def convert_to_ui_recipe(recipe: RecipeResponse) -> RecipeForUI:
    cleaned_ingredients = clean_ingredients(recipe.ingredients)
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
        steps=cleaned_steps,
    )
