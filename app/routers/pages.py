from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "index.html"


@router.get("/")
async def root():
    return FileResponse(TEMPLATE_PATH)
