import os
import json
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from bs4 import BeautifulSoup
from ..models import RecipeResponse, RecipeForUI, UpdateRecipe
from ..utils import fetch_html
from ..extraction import ai_extract, ai_refine_missing_fields, heuristic_extract
from ..db import save_recipe, get_all_recipes, delete_by_source_url, update_recipe_row
from ..config import UPLOAD_DIR

router = APIRouter()


def _is_valid_recipe(r: RecipeResponse) -> bool:
    has_title = bool((r.title or "").strip())
    has_ings = bool(r.ingredients)
    has_steps = bool(r.steps)
    return has_title or (has_ings and has_steps)


@router.post("/extract-recipe", response_model=RecipeResponse)
def extract(url: str):
    try:
        html = fetch_html(url)
    except Exception as e:
        if hasattr(e, "response") and getattr(e.response, "status_code", None) is not None:
            status = e.response.status_code
            raise HTTPException(status_code=502, detail=f"Failed to fetch page (HTTP {status}). The site may be blocking automated requests.")
        raise HTTPException(status_code=502, detail="Failed to fetch page. Please try another URL.")

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    try:
        recipe, _raw_ai = ai_extract(text, url)
        if _is_valid_recipe(recipe):
            try:
                save_recipe(recipe)
            except Exception as db_err:
                print("DB save failed:", db_err)
            return recipe
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
        print("AI extraction failed:", e)

    recipe = heuristic_extract(soup, url)
    try:
        save_recipe(recipe)
    except Exception as db_err:
        print("DB save failed:", db_err)
    return recipe


@router.get("/recipes", response_model=List[RecipeForUI])
def list_recipes():
    return get_all_recipes()


@router.delete("/recipes")
def delete_recipe(source_url: str):
    deleted = delete_by_source_url(source_url)
    return {"deleted": deleted}


@router.post("/recipes/upload-image")
def upload_recipe_image(source_url: str = Form(...), file: UploadFile = File(...)):
    content_type = file.content_type or ""
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    ext = allowed.get(content_type)
    if not ext:
        return {"error": f"Unsupported content type: {content_type}"}

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    import hashlib
    h = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    filename = f"{h}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, filename)
    with open(dest_path, "wb") as f:
        f.write(file.file.read())

    image_url = f"/uploads/{filename}"

    # Update stored image path directly using sqlite (reuse update function via minimal patch is overkill here)
    import sqlite3
    from ..config import DB_PATH
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


@router.patch("/recipes")
def update_recipe(update: UpdateRecipe):
    ok = update_recipe_row(update)
    if not ok:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"ok": True}
