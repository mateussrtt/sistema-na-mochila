from fastapi import APIRouter

router = APIRouter(tags=["saúde"])


@router.get("/health")
def health() -> dict[str, str]:
    """Indica se a API está no ar."""
    return {"status": "ok"}
