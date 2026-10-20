import logging
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Learning Note (Local Embeddings):
    Converts text chunks into 768-dimension number vectors using Ollama's
    'nomic-embed-text' model. Running this locally means our legal documents
    are never sent to external APIs like OpenAI.
    """
    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER.lower()
        self.base_url = settings.EMBEDDING_BASE_URL.rstrip("/")
        # Newer Ollama versions use /api/embed for batch embeddings
        if self.base_url.endswith("/v1"):
            root = self.base_url[:-3].rstrip("/")
            self.embed_url = f"{root}/api/embed"
            self.v1_url = f"{self.base_url}/embeddings"
        else:
            self.embed_url = f"{self.base_url}/api/embed"
            self.v1_url = f"{self.base_url}/v1/embeddings"

        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS or 768

    async def get_embedding(self, text: str) -> List[float]:
        """Create a vector embedding for a single search query."""
        embeddings = await self.get_embeddings_batch([text])
        return embeddings[0] if embeddings else [0.0] * self.dimensions

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple chunks at once (batching)
        so uploading a multi-page PDF is much faster.
        """
        if not texts:
            return []

        cleaned_texts = [t.strip() if t and t.strip() else "empty" for t in texts]

        # 1. Try native Ollama /api/embed endpoint first (fastest for batching)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(
                    self.embed_url,
                    json={
                        "model": self.model,
                        "input": cleaned_texts,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get("embeddings", [])
                    if len(embeddings) == len(cleaned_texts):
                        return embeddings
        except Exception as e:
            logger.warning(f"Ollama /api/embed attempt failed: {e}. Falling back...")

        # 2. Fallback to OpenAI-compatible /v1/embeddings
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(
                    self.v1_url,
                    headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY or 'ollama'}"},
                    json={
                        "model": self.model,
                        "input": cleaned_texts,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    raw_data = data.get("data", [])
                    raw_data.sort(key=lambda x: x.get("index", 0))
                    embeddings = [item["embedding"] for item in raw_data]
                    if len(embeddings) == len(cleaned_texts):
                        return embeddings
        except Exception as e:
            logger.error(f"Ollama /v1/embeddings attempt failed: {e}")

        # 3. Fallback: single item generation
        results: List[List[float]] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for text in cleaned_texts:
                res = await client.post(
                    self.embed_url,
                    json={"model": self.model, "input": text},
                )
                res.raise_for_status()
                data = res.json()
                emb = data.get("embeddings", [[]])[0]
                results.append(emb)

        return results


embedding_service = EmbeddingService()
