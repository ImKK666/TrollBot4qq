"""User profile services backed by GraphRAG."""

from __future__ import annotations

from typing import Any, Dict

from services.graphrag_manager import (create_attitude_document,
                                       store_documents, summarise_user)


async def get_user_profile(user_id: int, nickname: str) -> Dict[str, Any]:
    """Retrieve an aggregated view of a user's behaviour from GraphRAG."""
    summary = await summarise_user(user_id)
    profile = {
        "user_id": user_id,
        "nickname": nickname,
        "summary": summary.get("combined_text", ""),
        "aliases": summary.get("aliases", []),
        "attitudes": summary.get("attitudes", []),
        "memories": summary.get("memories", []),
    }
    return profile


async def update_user_summary(user_id: int, summary_text: str):
    """Compatibility wrapper retained for legacy callers."""
    # Summaries are derived from GraphRAG dynamically, so this becomes a no-op.
    return None


async def add_new_alias(user_id: int, alias: str):
    """Compatibility wrapper retained for legacy callers."""
    # Alias information will be discovered from GraphRAG memories.
    return None


async def update_attitudes(user_id: int, target_user_id: int, attitude_desc: str):
    """Record a social attitude observation inside GraphRAG."""
    doc = create_attitude_document(user_id, target_user_id, attitude_desc)
    await store_documents([doc])
