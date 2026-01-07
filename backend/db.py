import json
import sqlite3
import hashlib
import time
from typing import List, Optional, Tuple
from .config import DB_PATH
from .models import RecipeResponse, RecipeForUI, IngredientsSection, StepsSection, UpdateRecipe
from .extraction import convert_to_ui_recipe


def init_db() -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
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
        try:
            cur.execute("ALTER TABLE recipes ADD COLUMN image_url TEXT")
        except sqlite3.OperationalError:
            pass
        con.commit()
    finally:
        con.close()


def save_recipe(recipe: RecipeResponse) -> int:
    ui_recipe = convert_to_ui_recipe(recipe)
    source_url = (recipe.source_url or "").strip()
    if not source_url:
        seed = f"{recipe.title}|{(recipe.steps[0] if recipe.steps else '')}|{time.time()}".encode("utf-8")
        h = hashlib.sha256(seed).hexdigest()[:16]
        source_url = f"generated:{h}"

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
        cur.execute(
            """
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
            """,
            (
                ui_recipe.title,
                ui_recipe.author,
                source_url,
                int(ui_recipe.prep_time or 0),
                int(ui_recipe.cook_time or 0),
                int(ui_recipe.total_time or 0),
                ui_recipe.servings,
                ingredients_json,
                steps_json,
            ),
        )
        con.commit()
        cur.execute("SELECT id FROM recipes WHERE source_url = ?", (source_url,))
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        con.close()


def get_all_recipes() -> List[RecipeForUI]:
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
            ingredients_data = json.loads(ing_json) if ing_json else []
            ingredients_sections = [
                IngredientsSection(section=s.get("section", "Ingredients"), items=s.get("items", []))
                for s in ingredients_data
            ]
            steps_sections: List[StepsSection] = []
            if steps_json:
                try:
                    steps_data = json.loads(steps_json)
                except Exception:
                    steps_data = []
                if isinstance(steps_data, list):
                    if steps_data and isinstance(steps_data[0], str):
                        steps_sections = [StepsSection(section="Steps", items=steps_data)]
                    else:
                        for s in steps_data:
                            if isinstance(s, dict):
                                steps_sections.append(
                                    StepsSection(section=s.get("section", "Steps"), items=s.get("items", []))
                                )
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
                    steps=steps_sections,
                )
            )
        return out
    finally:
        con.close()


def delete_by_source_url(source_url: str) -> int:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM recipes WHERE source_url = ?", (source_url,))
        con.commit()
        return cur.rowcount
    finally:
        con.close()


def get_recipe_row_by_source_url(source_url: str):
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT title, author, prep_time, cook_time, total_time, servings, ingredients_json, steps_json
            FROM recipes WHERE source_url = ?
            """,
            (source_url,),
        )
        return cur.fetchone()
    finally:
        con.close()


def update_recipe_row(update: UpdateRecipe) -> bool:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM recipes WHERE source_url = ?", (update.source_url,))
        row = cur.fetchone()
        if row is None:
            return False
        columns = [col[0] for col in cur.description]
        row_dict = dict(zip(columns, row))
        changes = update.dict(exclude_unset=True)
        for key, value in changes.items():
            if key == "ingredients":
                value = json.dumps([
                    {"section": s.section, "items": s.items}
                    for s in convert_to_ui_recipe(RecipeResponse(
                        title=row_dict.get("title") or "",
                        author=row_dict.get("author") or "",
                        source_url=update.source_url,
                        prep_time=row_dict.get("prep_time") or 0,
                        cook_time=row_dict.get("cook_time") or 0,
                        total_time=row_dict.get("total_time") or 0,
                        servings=row_dict.get("servings") or "",
                        ingredients=changes.get("ingredients", []),
                        steps=json.loads(row_dict.get("steps_json") or "[]") if isinstance(row_dict.get("steps_json"), str) else []
                    )).ingredients
                ])
                key = "ingredients_json"
            elif key == "steps":
                value = json.dumps([
                    {"section": s.section, "items": s.items}
                    for s in convert_to_ui_recipe(RecipeResponse(
                        title=row_dict.get("title") or "",
                        author=row_dict.get("author") or "",
                        source_url=update.source_url,
                        prep_time=row_dict.get("prep_time") or 0,
                        cook_time=row_dict.get("cook_time") or 0,
                        total_time=row_dict.get("total_time") or 0,
                        servings=row_dict.get("servings") or "",
                        ingredients=json.loads(row_dict.get("ingredients_json") or "[]") if isinstance(row_dict.get("ingredients_json"), str) else [],
                        steps=changes.get("steps", []),
                    )).steps
                ])
                key = "steps_json"
            cur.execute(
                f"UPDATE recipes SET {key} = ? WHERE source_url = ?",
                (value, update.source_url),
            )
            con.commit()
        return True
    finally:
        con.close()


def db_health_info():
    result = {"ok": False, "db_path": DB_PATH}
    con = None
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("PRAGMA integrity_check;")
        integrity = cur.fetchone()
        result["integrity"] = integrity[0] if integrity else None
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recipes'")
        table_exists = cur.fetchone() is not None
        result["recipes_table"] = table_exists
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
