"""
LangGraph node — RBAC router.

Builds Qdrant payload filter from user's role (server-side from JWT).
Stores filter in state for retriever node to use.
Logs routing decision to audit trail.

Does NO retrieval — only builds and stores filter.

Error handling:
    - Catches all exceptions
    - Sets blocked state on error
    - Never exposes internal errors
"""

import logging

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event, log_rbac_route
from backend.retrieval.rbac_filter import build_rbac_filter

logger = logging.getLogger(__name__)


async def rbac_router(state: RAGState) -> RAGState:
    """
    LangGraph node — build RBAC filter and store in state.

    Steps:
        1. Read role from state (server-side from JWT, never client-supplied)
        2. Build Qdrant payload filter via rbac_filter.build_rbac_filter()
        3. Store filter in state["rbac_filter"] for retriever
        4. Log routing decision to audit trail

    Args:
        state: Current RAGState with role set from JWT

    Returns:
        Updated RAGState with rbac_filter populated
    """
    role = state.get("role", "")
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "")

    try:
        # ── Build filter (server-side, immutable) ──────────────────
        rbac_filter = build_rbac_filter(role)

        # ── Store in state for retriever node ──────────────────────
        state["rbac_filter"] = rbac_filter.model_dump()

        # ── Log routing decision ───────────────────────────────────
        filter_summary = _summarize_filter(rbac_filter, role)
        log_rbac_route(
            user_id=user_id,
            session_id=session_id,
            role=role,
            filter_summary=filter_summary,
        )

        return state

    except Exception as e:
        # ── Graceful failure ───────────────────────────────────────
        logger.error(f"RBAC router error: {e}")
        log_event(
            event_type="rbac_router_error",
            user_id=user_id,
            session_id=session_id,
            role=role,
            details={"error": str(e)[:200]},
        )
        state["blocked"] = True
        state["block_reason"] = "routing_error"
        state["rbac_filter"] = None
        state["guardrail_triggered"] = True
        return state


def _summarize_filter(rbac_filter, role: str) -> dict:
    """Create human-readable summary of filter for audit log."""
    summary = {
        "role": role,
        "must_conditions": len(rbac_filter.must),
        "has_should_conditions": rbac_filter.should is not None,
    }

    conditions = []
    for condition in rbac_filter.must:
        if hasattr(condition, "key"):
            conditions.append(f"{condition.key}={condition.match.value}")
    summary["must_fields"] = conditions

    if rbac_filter.should:
        summary["should_branches"] = len(rbac_filter.should)

    return summary
