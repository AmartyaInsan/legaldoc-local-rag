from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    id: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    system_prompt: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None
    search_mode: Optional[str] = "hybrid"  # "hybrid", "vector", "keyword"
    subagent_model: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "assistant"
    content: str
    model: str
    thread_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Thread(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Conversation"
    is_pinned: bool = False
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: Optional[str] = None


class ThreadCreate(BaseModel):
    title: Optional[str] = "New Conversation"


class ThreadUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
