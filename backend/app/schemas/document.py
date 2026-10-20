from typing import Optional, Dict, Any
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    content_hash: Optional[str] = None
    status: str
    chunk_count: int = 0
    doc_action: Optional[str] = "created"
    metadata: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
