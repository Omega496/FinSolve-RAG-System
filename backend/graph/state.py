"""
RAGState — canonical state definition for LangGraph pipeline.

TypedDict ensures type safety across all graph nodes.
Factory function provides safe defaults for new queries.
"""

from typing import Optional, TypedDict


class RAGState(TypedDict):
    """
    State passed between all LangGraph nodes.

    Fields:
        query: User's natural language question
        role: Authenticated user's RBAC role (from JWT)
        session_id: Unique session identifier (UUID4)
        user_id: Employee ID (from JWT sub claim)
        conversation_history: Last 5 turns sliding window
        retrieved_chunks: Child chunks from Qdrant (hybrid retrieval)
        parent_chunks: Parent chunks after swap (richer context for LLM)
        response: Final LLM response text
        streamed_tokens: Tokens streamed to frontend (SSE)
        blocked: Whether query was blocked by guardrails
        block_reason: Why blocked (off_topic | prompt_injection | unauthorized | pii_detected)
        pii_detected: Whether PII found in LLM output
        guardrail_triggered: Whether any guardrail fired
        ragas_scores: RAGAS evaluation metrics (async)
        latency_ms: End-to-end latency in milliseconds
    """

    query: str
    role: str
    session_id: str
    user_id: str
    conversation_history: list[dict]
    retrieved_chunks: list[dict]
    parent_chunks: list[dict]
    response: str
    streamed_tokens: list[str]
    blocked: bool
    block_reason: Optional[str]
    pii_detected: bool
    guardrail_triggered: bool
    ragas_scores: Optional[dict]
    latency_ms: Optional[float]
    rbac_filter: Optional[dict]


# Valid block reasons (for validation)
VALID_BLOCK_REASONS = frozenset({
    "off_topic",
    "prompt_injection",
    "unauthorized",
    "pii_detected",
})


def create_initial_state(
    query: str,
    role: str,
    session_id: str,
    user_id: str,
    history: list[dict],
) -> RAGState:
    """
    Create RAGState with safe defaults for a new query.

    Args:
        query: User's question
        role: RBAC role from JWT (server-side only)
        session_id: UUID4 session identifier
        user_id: Employee ID from JWT sub claim
        history: Conversation history (up to 5 recent turns)

    Returns:
        RAGState with all fields initialized to safe defaults
    """
    return RAGState(
        query=query,
        role=role,
        session_id=session_id,
        user_id=user_id,
        conversation_history=history,
        retrieved_chunks=[],
        parent_chunks=[],
        response="",
        streamed_tokens=[],
        blocked=False,
        block_reason=None,
        pii_detected=False,
        guardrail_triggered=False,
        ragas_scores=None,
        latency_ms=None,
        rbac_filter=None,
    )
