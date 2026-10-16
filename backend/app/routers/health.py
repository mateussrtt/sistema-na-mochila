from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["saúde"])


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Indica se a API está no ar e se consegue falar com o banco."""
    try:
        db.execute(text("SELECT 1"))
        banco = "ok"
    except SQLAlchemyError:
        banco = "indisponivel"
    return {"status": "ok", "banco": banco}
