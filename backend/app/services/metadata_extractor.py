import json
import logging
import re
from typing import List, Optional
import httpx
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


# Learning Note:
# When a document is uploaded (Module 4), we ask the local Ollama model to read the first 1,500 characters
# and return a structured JSON summary (title, summary, document_type, keywords) validated by Pydantic.
# If Ollama is busy or fails, _fallback_metadata() extracts basic info using simple Python rules.

class ExtractedMetadata(BaseModel):
    title: str = Field(default="", description="Descriptive title of the document")
    summary: str = Field(default="", description="1-2 sentence executive summary of the document")
    document_type: str = Field(
        default="general",
        description=(
            "Category: legal, inventory, presentation, kpi_report, financial, "
            "technical, guide, report, notes, general"
        ),
    )
    keywords: List[str] = Field(
        default_factory=list, description="Top 3-6 key topic keywords or tags"
    )
    target_audience: Optional[str] = Field(
        default="general", description="Intended audience, e.g. executives, clients, legal team, operations, developers"
    )
    language: str = Field(default="id", description="Primary language of the document (id, en, or bilingual)")


class MetadataExtractor:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY or "ollama"
        self.model = settings.LLM_MODEL
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(45.0, connect=5.0),
        )

    def _infer_domain_type(self, filename: str, text_sample: str) -> str:
        """Heuristic domain classifier for Legal, Inventory, Client Presentation, KPI Report, Financial, Technical."""
        combined = f"{filename} {text_sample[:1200]}".lower()
        if any(w in combined for w in ["inventaris", "inventory", "stok", "stock", "sku", "gudang", "warehouse", "reorder", "unit price", "qty", "kuantitas"]):
            return "inventory"
        if any(w in combined for w in ["kpi", "key performance", "okr", "q1", "q2", "q3", "q4", "target vs", "realisasi", "capaian kinerja", "metrik kinerja", "scorecard"]):
            return "kpi_report"
        if filename.lower().endswith(".pptx") or any(w in combined for w in ["--- slide ", "pitch deck", "client presentation", "presentasi klien", "proposal klien", "deck", "agenda presentasi"]):
            return "presentation"
        if any(w in combined for w in ["undang-undang", "peraturan", "permenkum", "pasal", "ayat", "merek", "paten", "hukum", "regulasi", "statute", "law", "regulation"]):
            return "legal"
        if any(w in combined for w in ["laporan keuangan", "financial", "balance sheet", "neraca", "laba rugi", "revenue", "ebitda", "budget", "anggaran"]):
            return "financial"
        if any(w in combined for w in ["panduan", "guide", "sop", "manual", "tutorial", "prosedur operasional"]):
            return "guide"
        if any(w in combined for w in ["architecture", "api", "kode", "sistem", "technical", "teknis", "spesifikasi"]):
            return "technical"
        return "general"

    def _detect_doc_language(self, text_sample: str) -> str:
        """Detect whether the document text is primarily Indonesian ('id') or English ('en')."""
        sample_lower = text_sample.lower()
        id_words = len(re.findall(r"\b(?:yang|dan|di|untuk|dengan|pada|dalam|adalah|dari|ini|itu|pasal|atau|oleh|tidak|akan|telah)\b", sample_lower))
        en_words = len(re.findall(r"\b(?:the|and|for|with|that|this|from|are|was|were|have|has|will|shall|section|article|target|client)\b", sample_lower))
        if id_words > en_words * 1.2:
            return "id"
        elif en_words > id_words * 1.2:
            return "en"
        return "id" if id_words >= en_words else "en"

    def _fallback_metadata(self, filename: str, text_sample: str) -> ExtractedMetadata:
        """Fallback heuristics if LLM extraction fails or is unavailable."""
        clean_name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        first_line = text_sample.strip().split("\n")[0].strip("# -").strip()
        title = first_line[:65] if len(first_line) > 3 else clean_name

        words = re.findall(r"\b[A-Za-z]{4,}\b", text_sample.lower())
        common_words = {
            "this", "that", "with", "from", "have", "were", "which", "there", "about", "project",
            "yang", "untuk", "dengan", "dalam", "pada", "adalah", "dari", "oleh", "atau", "tidak", "slide", "page"
        }
        keywords = list(dict.fromkeys([w for w in words if w not in common_words]))[:5]
        inferred_type = self._infer_domain_type(filename, text_sample)
        detected_lang = self._detect_doc_language(text_sample)

        return ExtractedMetadata(
            title=title,
            summary=f"Document '{filename}' ({inferred_type}) containing {len(text_sample)} characters of text.",
            document_type=inferred_type,
            keywords=keywords if keywords else ["document", inferred_type],
            language=detected_lang,
        )

    async def extract_metadata(self, filename: str, text_content: str) -> ExtractedMetadata:
        """
        Use Ollama qwen2.5:7b to extract structured metadata from document text across Legal,
        Inventory, Client Presentation, KPI Report, Financial, and Technical domains.
        Validated with Pydantic.
        """
        if not text_content or not text_content.strip():
            return self._fallback_metadata(filename, "")

        # Take first 1500 chars which usually contains title, intro, and headers
        sample = text_content.strip()[:1500]
        heuristic_type = self._infer_domain_type(filename, sample)
        heuristic_lang = self._detect_doc_language(sample)

        prompt = f"""You are an expert enterprise & legal document cataloger. Analyze this document excerpt and extract structured metadata.

FILENAME: {filename}
EXCERPT:
{sample}

Extract a JSON object matching this schema:
{{
  "title": "Concise, descriptive title",
  "summary": "1-2 sentence executive summary of key takeaways and topics",
  "document_type": "One of: legal, inventory, presentation, kpi_report, financial, technical, guide, report, notes, general",
  "keywords": ["3-5", "relevant", "keywords"],
  "target_audience": "e.g. legal counsel, executives, clients, operations, developers, general",
  "language": "id or en"
}}

Respond ONLY with the JSON object, with no markdown code fences or conversational text."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a specialized JSON-only metadata extraction service. You output ONLY valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            raw_reply = response.choices[0].message.content or "{}"
            raw_reply = raw_reply.strip()
            if raw_reply.startswith("```json"):
                raw_reply = raw_reply[7:]
            if raw_reply.startswith("```"):
                raw_reply = raw_reply[3:]
            if raw_reply.endswith("```"):
                raw_reply = raw_reply[:-3]

            parsed_dict = json.loads(raw_reply.strip())
            metadata = ExtractedMetadata.model_validate(parsed_dict)

            # Ensure specialized domain types (inventory, kpi_report, presentation, legal) aren't lost to 'general'
            valid_types = {
                "legal", "inventory", "presentation", "kpi_report",
                "financial", "technical", "guide", "report", "notes", "general"
            }
            if metadata.document_type not in valid_types or (metadata.document_type == "general" and heuristic_type != "general"):
                metadata.document_type = heuristic_type
            if metadata.language not in ("id", "en"):
                metadata.language = heuristic_lang

            logger.info(
                f"Successfully extracted metadata for {filename}: title='{metadata.title}', "
                f"type='{metadata.document_type}', lang='{metadata.language}'"
            )
            return metadata

        except Exception as e:
            logger.warning(f"LLM metadata extraction failed for {filename}: {e}. Using fallback heuristics.")
            return self._fallback_metadata(filename, sample)


metadata_extractor = MetadataExtractor()
