"""
RAGAS evaluation — async, non-blocking.

Runs faithfulness, answer_relevancy, context_precision, context_recall.
Results stored in audit log. Never blocks main pipeline.
"""

import asyncio
import os
import traceback
from typing import Optional

from .audit_logger import log_event

# ─── RAGAS Import (graceful fallback) ──────────────────────────────────
_RAGAS_AVAILABLE = False
_evaluate = None
_metrics = {}

try:
    from ragas import evaluate as _evaluate_fn
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )

    _evaluate = _evaluate_fn
    _metrics = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
    }
    _RAGAS_AVAILABLE = True
except ImportError:
    pass

# ─── Configuration ─────────────────────────────────────────────────────
# Skip evaluation if response is too short (not meaningful)
MIN_RESPONSE_LENGTH = 10
# Skip evaluation if no contexts retrieved
MIN_CONTEXTS = 1


async def evaluate(
    query: str,
    response: str,
    retrieved_chunks: list[dict],
    session_id: str,
    user_id: str,
    role: str,
    blocked: bool = False,
) -> Optional[dict]:
    """
    Run RAGAS evaluation asynchronously.

    Args:
        query: User's question
        response: LLM response
        retrieved_chunks: Retrieved chunk dicts with 'text' field
        session_id: Session UUID
        user_id: Employee ID
        role: User's RBAC role
        blocked: Whether query was blocked (skip if True)

    Returns:
        RAGAS scores dict or None if skipped/failed
    """
    # ── Skip conditions ────────────────────────────────────────────
    if blocked:
        return None

    if not _RAGAS_AVAILABLE:
        _log_skip("ragas_not_installed", session_id, user_id, role)
        return None

    if len(response) < MIN_RESPONSE_LENGTH:
        _log_skip("response_too_short", session_id, user_id, role)
        return None

    contexts = [
        chunk.get("text", "")
        for chunk in retrieved_chunks
        if chunk.get("text")
    ]

    if len(contexts) < MIN_CONTEXTS:
        _log_skip("no_contexts", session_id, user_id, role)
        return None

    # ── Run evaluation ─────────────────────────────────────────────
    try:
        scores = await _run_ragas_evaluation(query, response, contexts)

        # ── Log scores to audit ────────────────────────────────────
        log_event(
            event_type="ragas_evaluation",
            user_id=user_id,
            session_id=session_id,
            role=role,
            details={
                "scores": scores,
                "query_preview": query[:100],
            },
        )

        return scores

    except Exception as e:
        # ── Graceful failure — log but never crash ─────────────────
        log_event(
            event_type="ragas_evaluation_error",
            user_id=user_id,
            session_id=session_id,
            role=role,
            details={
                "error": str(e),
                "query_preview": query[:100],
            },
        )
        return None


async def _run_ragas_evaluation(
    query: str,
    response: str,
    contexts: list[str],
) -> dict:
    """
    Execute RAGAS evaluation in thread pool (non-blocking).

    Args:
        query: User's question
        response: LLM response
        contexts: List of context strings

    Returns:
        Dict of metric scores
    """
    # Build evaluation dataset
    # RAGAS expects specific format
    eval_data = {
        "question": [query],
        "answer": [response],
        "contexts": [contexts],
        "ground_truth": [""],  # No ground truth available
    }

    # Run in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _evaluate(
            dataset=eval_data,
            metrics=list(_metrics.values()),
        ),
    )

    # Extract scores
    scores = {}
    for metric_name in _metrics.keys():
        if metric_name in result:
            scores[metric_name] = result[metric_name]
        else:
            scores[metric_name] = None

    return scores


def _log_skip(
    reason: str,
    session_id: str,
    user_id: str,
    role: str,
) -> None:
    """Log why evaluation was skipped."""
    log_event(
        event_type="ragas_skipped",
        user_id=user_id,
        session_id=session_id,
        role=role,
        details={"reason": reason},
    )


def trigger_async_evaluation(
    query: str,
    response: str,
    retrieved_chunks: list[dict],
    session_id: str,
    user_id: str,
    role: str,
    blocked: bool = False,
) -> None:
    """
    Fire-and-forget RAGAS evaluation.
    Creates background task — does not block response.

    Args:
        query: User's question
        response: LLM response
        retrieved_chunks: Retrieved chunks with metadata
        session_id: Session UUID
        user_id: Employee ID
        role: User's RBAC role
        blocked: Whether query was blocked
    """
    asyncio.create_task(
        evaluate(
            query=query,
            response=response,
            retrieved_chunks=retrieved_chunks,
            session_id=session_id,
            user_id=user_id,
            role=role,
            blocked=blocked,
        )
    )


def is_ragas_available() -> bool:
    """Check if RAGAS is installed and available."""
    return _RAGAS_AVAILABLE
