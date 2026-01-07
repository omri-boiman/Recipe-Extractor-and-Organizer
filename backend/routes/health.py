from fastapi import APIRouter
from ..db import db_health_info

router = APIRouter()

@router.get("/db-health")
def db_health():
    return db_health_info()
