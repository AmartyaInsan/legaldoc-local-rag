from fastapi import APIRouter
from app.core.config import settings
from app.services.llm import llm_service
from app.services.local_db import local_db_service

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Check if local Ollama and local databases (ChromaDB + SQLite) are running properly.
    """
    llm_health = await llm_service.check_health()
    db_health = local_db_service.check_health()

    overall_status = "healthy"
    if llm_health.get("status") != "online" or db_health.get("status") != "connected":
        overall_status = "degraded"

    return {
        "status": overall_status,
        "environment": settings.ENVIRONMENT,
        "project": settings.PROJECT_NAME,
        "services": {
            "llm": llm_health,
            "local_db": db_health,
        },
        "config": {
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "langsmith_tracing": settings.LANGSMITH_TRACING,
        },
    }
