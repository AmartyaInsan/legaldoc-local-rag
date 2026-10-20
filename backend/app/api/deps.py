from fastapi import Header
from typing import Optional, Dict, Any


async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Learning Note (Local User Session):
    Since this RAG system is modified to run in a local close-environment
    (without cloud auth), we return a default local user profile.
    """
    return {"id": "local-user", "email": "user@localhost"}
