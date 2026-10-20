import sys
import os
import asyncio
import time
import json

# Use a portable relative path so this script works on any computer after cloning from GitHub
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.local_db import local_db_service
from app.services.llm import llm_service
from app.schemas.chat import ChatMessage
from app.services.retrieval import retrieval_service

async def main():
    print("=== TEST 1: Thread Rename & Pin in SQLite ===")
    # 1. Create a test thread
    test_thread = local_db_service.create_or_get_thread(
        thread_id="test-rename-pin-123",
        title="Original Title",
        user_id="test-user"
    )
    print(f"Created thread: {test_thread['id']}, title: '{test_thread['title']}', is_pinned: {test_thread.get('is_pinned')}")

    # 2. Rename thread
    renamed = local_db_service.update_thread(
        thread_id="test-rename-pin-123",
        title="Renamed Research Thread"
    )
    print(f"Renamed thread title: '{renamed['title']}'")
    assert renamed["title"] == "Renamed Research Thread", "Thread title should be updated"

    # 3. Pin thread
    pinned = local_db_service.update_thread(
        thread_id="test-rename-pin-123",
        is_pinned=True
    )
    print(f"Pinned thread is_pinned: {pinned['is_pinned']}")
    assert pinned["is_pinned"] is True, "Thread should be pinned"

    # 4. Check list_threads ordering: pinned thread must be at index 0
    threads = local_db_service.list_threads()
    first_thread = threads[0]
    print(f"First thread in list: '{first_thread['title']}', is_pinned: {first_thread.get('is_pinned')}")
    assert first_thread["id"] == "test-rename-pin-123", "Pinned thread must appear at top of list"

    # 5. Unpin thread
    unpinned = local_db_service.update_thread(
        thread_id="test-rename-pin-123",
        is_pinned=False
    )
    print(f"Unpinned thread is_pinned: {unpinned['is_pinned']}")
    assert unpinned["is_pinned"] is False, "Thread should be unpinned"

    # Clean up test thread
    local_db_service.delete_thread("test-rename-pin-123")
    print("PASSED TEST 1: Thread Rename & Pin fully operational!")

    print("\n=== TEST 2: LLM Time-To-First-Token (TTFT) & Streaming Latency ===")
    query = "Apa fungsi utama merek dalam perdagangan menurut dokumen?"
    results = await retrieval_service.retrieve_relevant_chunks(query, top_k=3, search_mode="hybrid")
    context = retrieval_service.format_rag_context(results)

    system_prompt = (
        "Anda adalah Analis Riset AI Ahli dalam sistem Agentic RAG Close-Environment.\n"
        "Jawab dalam Bahasa Indonesia secara lugas, berbobot, dan akurat (2-3 kalimat)."
    )
    messages = [ChatMessage(role="user", content=f"{context}\n\nPERTANYAAN: {query}")]

    t_start = time.time()
    first_token_time = None
    token_count = 0
    full_text = []

    async for chunk in llm_service.stream_chat(
        messages=messages,
        system_prompt=system_prompt,
        temperature=0.3
    ):
        if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
            try:
                payload = json.loads(chunk[6:].strip())
                token = payload.get("token", "")
                if token:
                    if first_token_time is None:
                        first_token_time = time.time() - t_start
                    token_count += 1
                    full_text.append(token)
            except Exception:
                pass

    total_time = time.time() - t_start
    generated = "".join(full_text).strip()
    print(f"Time-To-First-Token (TTFT): {first_token_time:.2f}s" if first_token_time else "No tokens received")
    print(f"Total tokens: {token_count}, Total time: {total_time:.2f}s, Speed: {token_count / total_time:.1f} tokens/s")
    print(f"Generated sample:\n{generated[:200]}...")
    assert first_token_time is not None and first_token_time < 3.0, f"TTFT should be under 3s, got {first_token_time}"
    assert len(generated) > 20, "Should generate a substantive response"
    print("PASSED TEST 2: Instant streaming with zero pause!")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
