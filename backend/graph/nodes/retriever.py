"""
LangGraph node — hybrid retrieval.

Calls hybrid_retriever with query + role (RBAC filter applied internally).
Stores child chunks in state. Tracks latency. Blocks if no results.

Error handling:
    - Retry logic (3 attempts, exponential backoff) for Qdrant queries
    - Catches all exceptions, sets blocked state
    - Never exposes internal errors to client
"""

import asyncio
import logging
import time

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event, log_query
from backend.retrieval.hybrid_retriever import hybrid_retrieve

logger = logging.getLogger(__name__)

# ─── Retry Configuration ───────────────────────────────────────────────
MAX_RETRIES = 3
BASE_DELAY = 0.5  # seconds


async def _retrieve_with_retry(query: str, role: str) -> list:
    """
    Call hybrid_retrieve with exponential backoff retry.
    
    Args:
        query: User's query
        role: User's RBAC role
        
    Returns:
        List of RetrievedChunk objects
    """
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(
                None,
                lambda: hybrid_retrieve(query=query, role=role)
            )
            return chunks
            
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)  # exponential backoff
                logger.warning(f"Retrieval attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Retrieval failed after {MAX_RETRIES} attempts: {e}")
    
    raise last_error


async def retriever(state: RAGState) -> RAGState:
    """
    LangGraph node — retrieve child chunks from Qdrant.

    Steps:
        1. Record start time
        2. Call hybrid_retrieve(query, role) with retry logic
        3. Convert RetrievedChunk objects to dicts for state storage
        4. If no chunks found: block query
        5. Record latency

    Error handling:
        - 3 retries with exponential backoff
        - Catches all exceptions
        - Sets blocked state on failure
    """
    query = state["query"]
    role = state["role"]
    user_id = state["user_id"]
    session_id = state["session_id"]

    try:
        # ── Step 1: Record start time ──────────────────────────────
        start_time = time.monotonic()

        # ── Step 2: Retrieve with retry ────────────────────────────
        chunks = await _retrieve_with_retry(query=query, role=role)

        # ── Step 3: Record end time ────────────────────────────────
        end_time = time.monotonic()
        latency_ms = (end_time - start_time) * 1000

        # ── Step 4: Convert to dicts for state storage ─────────────
        chunk_dicts = []
        for chunk in chunks:
            chunk_dicts.append({
                "id": chunk.id,
                "score": chunk.score,
                "payload": chunk.payload,
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "header_breadcrumb": chunk.header_breadcrumb,
                "source_file": chunk.source_file,
                "parent_id": chunk.parent_id,
                "is_atomic": chunk.is_atomic,
            })

        # ── Step 5: Store in state ─────────────────────────────────
        state["retrieved_chunks"] = chunk_dicts

        # ── Step 6: Block if no chunks found ───────────────────────
        if not chunk_dicts:
            state["blocked"] = True
            state["block_reason"] = "no_relevant_documents"
            state["guardrail_triggered"] = True

        # ── Step 7: Log query metrics ──────────────────────────────
        log_query(
            user_id=user_id,
            session_id=session_id,
            role=role,
            query=query,
            chunks_retrieved=len(chunk_dicts),
            latency_ms=latency_ms,
        )

        return state

    except Exception as e:
        # ── Graceful failure ───────────────────────────────────────
        logger.error(f"Retriever error: {e}")
        log_event(
            event_type="retrieval_error",
            user_id=user_id,
            session_id=session_id,
            role=role,
            details={"error": str(e)[:200]},
        )
        state["blocked"] = True
        state["block_reason"] = "retrieval_error"
        state["retrieved_chunks"] = []
        state["guardrail_triggered"] = True
        return state
