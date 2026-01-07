from typing import List, Optional
from pydantic import BaseModel

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

class ChatQuestionRequest(BaseModel):
    source_url: str
    question: str

class UpdateRecipe(BaseModel):
    source_url: str
    title: Optional[str] = None
    author: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    total_time: Optional[int] = None
    servings: Optional[str] = None
    ingredients: Optional[List[str]] = None
    steps: Optional[List[str]] = None
