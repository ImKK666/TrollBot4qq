"""Memory services backed by the GraphRAG knowledge graph."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from bot_config import MEMORY_SEARCH_FINAL_MAX_COUNT
from services.graphrag_manager import (GraphDocument,
                                       create_conversation_document,
                                       create_memory_document,
                                       search_documents, store_documents)


async def add_memory(
    user_id: int,
    message_id: int,
    original_text: str,
    summary_text: str,
    troll_potential: int,
    timestamp: int,
) -> bool:
    """Persist a single memorable event for a user."""
    doc = create_memory_document(
        user_id=user_id,
        message_id=message_id,
        original_text=original_text,
        summary_text=summary_text,
        troll_potential=troll_potential,
        timestamp=timestamp,
    )
    await store_documents([doc])
    return True


async def add_conversation_snapshot(
    group_id: int,
    start_time: int,
    end_time: int,
    theme: str,
    summary: str,
    participants_viewpoints: Dict[int, str],
) -> None:
    """Persist a summarised conversation window as a GraphRAG document."""
    doc = create_conversation_document(
        group_id=group_id,
        start_time=start_time,
        end_time=end_time,
        summary=f"{theme}: {summary}",
        participants=participants_viewpoints,
    )
    await store_documents([doc])


async def store_bulk_documents(docs: Iterable[GraphDocument]) -> None:
    """Helper to persist multiple documents at once."""
    await store_documents(list(docs))


async def search_relevant_memories(
    query_text: str,
    user_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Search GraphRAG for memories matching a natural language query."""
    max_results = limit or MEMORY_SEARCH_FINAL_MAX_COUNT
    results = await search_documents(query_text, user_id=user_id, limit=max_results)

    formatted: List[Dict[str, Any]] = []
    for entry in results:
        formatted.append(
            {
                "id": entry.get("doc_id"),
                "original_text": entry.get("text"),
                "metadata": entry.get("metadata", {}),
                "distance": None,
            }
        )
    return formatted
