"""
LangGraph node — sliding window memory update.

Appends current turn to conversation history.
Enforces 5-turn sliding window (10 messages max).
Updates memory even for blocked queries (preserves context).

Error handling:
    - Catches all exceptions
    - Preserves existing history on error
    - Never exposes internal errors
"""

import logging

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────
MAX_TURNS = 5
MAX_MESSAGES = MAX_TURNS * 2  # 2 messages per turn (user + assistant)


async def memory_update(state: RAGState) -> RAGState:
    """
    LangGraph node — update conversation history with current turn.

    Steps:
        1. Create user and assistant message dicts
        2. Append to conversation_history
        3. Enforce sliding window (keep last 5 turns / 10 messages)
        4. Return updated state

    Memory is updated even for blocked queries so conversation
    context is preserved for future guardrail decisions.

    Error handling:
        - Preserves existing history on error
        - Never exposes internal errors

    Args:
        state: Current RAGState with query and response

    Returns:
        Updated RAGState with conversation_history updated
    """
    try:
        query = state.get("query", "")
        response = state.get("response", "")
        blocked = state.get("blocked", False)

        # ── Step 1: Create message dicts ───────────────────────────
        user_message = {"role": "user", "content": query}

        # For blocked queries, record the block reason in assistant message
        if blocked:
            block_reason = state.get("block_reason", "unknown")
            assistant_message = {
                "role": "assistant",
                "content": f"[BLOCKED: {block_reason}] {response}",
            }
        else:
            assistant_message = {"role": "assistant", "content": response}

        # ── Step 2: Append to history ──────────────────────────────
        history = state.get("conversation_history", [])
        history.append(user_message)
        history.append(assistant_message)

        # ── Step 3: Enforce sliding window ─────────────────────────
        if len(history) > MAX_MESSAGES:
            history = history[-MAX_MESSAGES:]

        # ── Step 4: Update state ───────────────────────────────────
        state["conversation_history"] = history

        return state

    except Exception as e:
        # ── Preserve existing history on error ─────────────────────
        logger.error(f"Memory update error: {e}")
        log_event(
            event_type="memory_update_error",
            user_id=state.get("user_id", "unknown"),
            session_id=state.get("session_id", ""),
            role=state.get("role", ""),
            details={"error": str(e)[:200]},
        )
        # Don't modify history on error — preserve existing state
        if "conversation_history" not in state:
            state["conversation_history"] = []
        return state
