from typing import List, Optional
from fastapi import APIRouter, HTTPException
from azure.ai.inference.models import SystemMessage, UserMessage
from ..models import ChatQuestionRequest
from ..db import get_recipe_row_by_source_url
from ..config import client, MODEL_NAME
import json

router = APIRouter()


@router.post("/recipes/ask")
def recipe_ask(req: ChatQuestionRequest):
    source_url = (req.source_url or "").strip()
    question = (req.question or "").strip()
    if not source_url or not question:
        raise HTTPException(status_code=400, detail="source_url and question are required")

    row = get_recipe_row_by_source_url(source_url)
    if not row:
        raise HTTPException(status_code=404, detail="Recipe not found for provided source_url")

    title, author, prep_time, cook_time, total_time, servings, ing_json, steps_json = row

    def mins_text(val: Optional[int]) -> str:
        try:
            v = int(val or 0)
        except Exception:
            v = 0
        return f"{v} min" if v else "N/A"

    try:
        ing_sections = json.loads(ing_json) if ing_json else []
    except Exception:
        ing_sections = []
    try:
        steps_data = json.loads(steps_json) if steps_json else []
    except Exception:
        steps_data = []

    steps_sections: List[dict] = []
    if isinstance(steps_data, list):
        if steps_data and isinstance(steps_data[0], str):
            steps_sections = [{"section": "Steps", "items": steps_data}]
        else:
            steps_sections = [
                {"section": (s or {}).get("section", "Steps"), "items": (s or {}).get("items", [])}
                for s in steps_data if isinstance(s, dict)
            ]

    lines: List[str] = []
    lines.append(f"Title: {title or ''}")
    lines.append(f"Author: {author or ''}")
    lines.append(f"Servings: {servings or ''}")
    lines.append(f"Prep time: {mins_text(prep_time)} | Cook time: {mins_text(cook_time)} | Total time: {mins_text(total_time)}")
    lines.append("")
    lines.append("Ingredients:")
    for sec in ing_sections or []:
        sec_name = (sec or {}).get("section", "Ingredients")
        items = (sec or {}).get("items", []) or []
        lines.append(f"  - {sec_name}:")
        for it in items:
            lines.append(f"      • {str(it)}")
    lines.append("")
    lines.append("Steps:")
    for sec in steps_sections or []:
        sec_name = (sec or {}).get("section", "Steps")
        items = (sec or {}).get("items", []) or []
        lines.append(f"  - {sec_name}:")
        for i, it in enumerate(items, start=1):
            lines.append(f"      {i}. {str(it)}")

    context_text = "\n".join(lines)

    system_prompt = (
        "You are a precise cooking assistant restricted to a single recipe. "
        "Answer ONLY questions directly related to this recipe's ingredients, steps, times, substitutions, "
        "serving adjustments, or basic techniques as applied to THIS recipe. "
        "If the user asks anything unrelated to this recipe, reply exactly: 'I can only answer questions about this recipe.'"
    )

    user_prompt = (
        "Recipe context (do not invent details beyond this):\n\n" +
        context_text +
        "\n\nUser question: " + question +
        "\n\nAnswer briefly and helpfully. If insufficient info, say what is missing based on the recipe."
    )

    try:
        resp = client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=user_prompt),
            ],
            model=MODEL_NAME,
        )
        answer = (resp.choices[0].message.content or "").strip()
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")
