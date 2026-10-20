from typing import AsyncGenerator, List, Dict, Any, Optional
import json
import logging
import httpx
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

class LLMService:
    """
    Learning Note (Module 2 - LLM Connection):
    Following the tutorial rules, we don't use LangChain or LangGraph here.
    Instead, we use the standard 'openai' Python SDK and point its base_url
    to our local Ollama server (http://localhost:11434/v1).
    """
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY or "ollama"
        self.default_model = settings.LLM_MODEL
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    async def check_health(self) -> Dict[str, Any]:
        """Check if the local Ollama service is running and list installed models."""
        try:
            if "localhost:11434" in self.base_url or self.provider == "ollama":
                # Check installed local models via Ollama's /api/tags endpoint
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get("http://localhost:11434/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m.get("name") for m in data.get("models", [])]
                        return {
                            "status": "online",
                            "provider": "ollama",
                            "active_model": self.default_model,
                            "available_models": models,
                        }
            # Fallback to OpenAI models list
            models_resp = await self.client.models.list()
            model_ids = [m.id for m in models_resp.data]
            return {
                "status": "online",
                "provider": self.provider,
                "active_model": self.default_model,
                "available_models": model_ids,
            }
        except Exception as e:
            logger.warning(f"LLM health check warning: {e}")
            return {
                "status": "degraded_or_offline",
                "provider": self.provider,
                "active_model": self.default_model,
                "error": str(e),
            }

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completions formatted as Server-Sent Events (SSE).
        Emits: data: {"token": "..."}\n\n
        End of stream: data: [DONE]\n\n
        """
        target_model = model or self.default_model

        # Assemble conversation messages
        formatted_msgs: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_msgs.append({"role": "system", "content": system_prompt})
        else:
            formatted_msgs.append({
                "role": "system",
                "content": (
                    "You are an expert, thoughtful AI research assistant in an Agentic RAG system. "
                    "Provide clear, accurate, and structured responses with syntax-highlighted code where helpful."
                )
            })

        for msg in messages:
            formatted_msgs.append({"role": msg.role, "content": msg.content})

        try:
            stream = await self.client.chat.completions.create(
                model=target_model,
                messages=formatted_msgs,
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    token = delta.content or ""
                    if token:
                        payload = json.dumps({"token": token, "finish_reason": chunk.choices[0].finish_reason})
                        yield f"data: {payload}\n\n"

            # Emit completion event
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in stream_chat: {e}", exc_info=True)
            err_payload = json.dumps({"error": str(e)})
            yield f"data: {err_payload}\n\n"
            yield "data: [DONE]\n\n"

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.4,
    ) -> str:
        """
        Execute non-streaming completion for isolated sub-agent tasks and analytical synthesis.
        """
        target_model = model or self.default_model
        msgs: List[Dict[str, Any]] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})

        try:
            resp = await self.client.chat.completions.create(
                model=target_model,
                messages=msgs,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error in complete: {e}", exc_info=True)
            return f"Error executing completion: {e}"


llm_service = LLMService()

