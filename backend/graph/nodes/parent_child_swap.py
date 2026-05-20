"""
LangGraph node — parent-child chunk swap.

Fetches parent chunks for richer LLM context.
Retains child chunks in state for source citations.

Error handling:
    - Catches all exceptions
    - Falls back to child chunks if parent fetch fails
    - Never exposes internal errors
"""

import logging

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event
from backend.retrieval.hybrid_retriever import (
    RetrievedChunk,
    parent_child_swap,
)

logger = logging.getLogger(__name__)


async def parent_child_swap_node(state: RAGState) -> RAGState:
    """
    LangGraph node — swap child chunks for parent chunks.

    Parent chunks (~400 tokens) provide richer context for LLM.
    Child chunks retained for precise source citations.

    Error handling:
        - If parent fetch fails, use child chunks as fallback
        - Never exposes internal errors

    Args:
        state: Current RAGState with retrieved_chunks populated

    Returns:
        Updated RAGState with parent_chunks populated
    """
    chunk_dicts = state.get("retrieved_chunks", [])

    if not chunk_dicts:
        state["parent_chunks"] = []
        return state

    try:
        # ── Step 1: Convert dicts to RetrievedChunk objects ────────
        child_chunks = [_dict_to_chunk(d) for d in chunk_dicts]

        # ── Step 2: Fetch parent chunks ────────────────────────────
        swap_result = parent_child_swap(child_chunks)

        # ── Step 3: Convert parent chunks to dicts ─────────────────
        parent_dicts = [
            _chunk_to_dict(chunk) for chunk in swap_result.parent_chunks
        ]

        # ── Step 4: Store in state ─────────────────────────────────
        state["parent_chunks"] = parent_dicts

        return state

    except Exception as e:
        # ── Fallback: use child chunks as parent chunks ────────────
        logger.error(f"Parent-child swap error, falling back to child chunks: {e}")
        log_event(
            event_type="parent_swap_error",
            user_id=state.get("user_id", "unknown"),
            session_id=state.get("session_id", ""),
            role=state.get("role", ""),
            details={"error": str(e)[:200], "fallback": "child_chunks"},
        )
        # Use child chunks as parent chunks (smaller context but still works)
        state["parent_chunks"] = chunk_dicts
        return state


def _dict_to_chunk(d: dict) -> RetrievedChunk:
    """Convert state dict to RetrievedChunk object."""
    return RetrievedChunk(
        id=d["id"],
        score=d["score"],
        payload=d["payload"],
    )


def _chunk_to_dict(chunk: RetrievedChunk) -> dict:
    """Convert RetrievedChunk to state dict."""
    return {
        "id": chunk.id,
        "score": chunk.score,
        "payload": chunk.payload,
        "text": chunk.text,
        "doc_id": chunk.doc_id,
        "header_breadcrumb": chunk.header_breadcrumb,
        "source_file": chunk.source_file,
        "parent_id": chunk.parent_id,
        "is_atomic": chunk.is_atomic,
    }
