"""
LangGraph node — PII output scanner.

Scans LLM response for PII using regex patterns from AGNNTS.md.
Blocks response if PII detected. Logs to audit trail (never logs matched content).

Error handling:
    - Catches all exceptions
    - Fails safe (blocks response if scanner error)
    - Never exposes internal errors
"""

import logging
import re

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event, log_guardrail_block

logger = logging.getLogger(__name__)

# ─── PII Patterns (verbatim from AGNNTS.md) ───────────────────────────
PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', "ssn"),
    (r'salary[\s:₹$£€]+[\d,]+', "salary"),
    (r'account[\s#:]+\d{6,}', "account_number"),
    (r'\b[A-Z]{2}\d{6}[A-Z]\b', "passport"),
    (r'\b\d{10}\b', "phone"),
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "email"),
    (r'pan[\s:]+[A-Z]{5}[0-9]{4}[A-Z]', "pan_card"),
    (r'aadhar[\s:]+\d{4}\s\d{4}\s\d{4}', "aadhar"),
]

# Pre-compile patterns for performance (case insensitive)
_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), pii_type)
    for pattern, pii_type in PII_PATTERNS
]

# Safe fallback message when PII detected
PII_FALLBACK_MESSAGE = (
    "I apologize, but I cannot provide this response as it may contain "
    "sensitive personal information. Please contact HR directly for "
    "queries involving employee personal data."
)


async def output_scanner(state: RAGState) -> RAGState:
    """
    LangGraph node — scan LLM response for PII.

    Steps:
        1. Run all PII regex patterns against response
        2. If any match:
           - Set state["pii_detected"] = True
           - Set state["blocked"] = True
           - Set state["block_reason"] = "pii_detected"
           - Replace response with safe fallback
           - Log to audit (pattern name only, never matched content)
        3. If no match:
           - Set state["pii_detected"] = False
           - Pass state through unchanged

    Error handling:
        - Fails safe (blocks response if scanner error)
        - Never exposes internal errors

    Args:
        state: Current RAGState with response from generator

    Returns:
        Updated RAGState with PII detection results
    """
    response = state.get("response", "")

    try:
        # ── Scan for PII ───────────────────────────────────────────
        detected_patterns = _scan_for_pii(response)

        if detected_patterns:
            # ── PII detected — block and replace ───────────────────
            state["pii_detected"] = True
            state["blocked"] = True
            state["block_reason"] = "pii_detected"
            state["response"] = PII_FALLBACK_MESSAGE
            state["streamed_tokens"] = [PII_FALLBACK_MESSAGE]

            # ── Log each detected pattern ──────────────────────────
            for pattern_name in detected_patterns:
                log_guardrail_block(
                    user_id=state.get("user_id", "unknown"),
                    session_id=state.get("session_id", ""),
                    role=state.get("role", ""),
                    block_reason=f"pii_detected:{pattern_name}",
                    query_preview=state.get("query", ""),
                )
        else:
            # ── No PII — pass through ──────────────────────────────
            state["pii_detected"] = False

        return state

    except Exception as e:
        # ── Fail safe: block response if scanner error ─────────────
        logger.error(f"Output scanner error (failing safe): {e}")
        log_event(
            event_type="output_scanner_error",
            user_id=state.get("user_id", "unknown"),
            session_id=state.get("session_id", ""),
            role=state.get("role", ""),
            details={"error": str(e)[:200], "action": "blocked_response"},
        )
        # Fail safe — block response if we can't scan it
        state["pii_detected"] = True
        state["blocked"] = True
        state["block_reason"] = "scanner_error"
        state["response"] = PII_FALLBACK_MESSAGE
        state["streamed_tokens"] = [PII_FALLBACK_MESSAGE]
        return state


def _scan_for_pii(text: str) -> list[str]:
    """
    Scan text for PII patterns.

    Args:
        text: Text to scan

    Returns:
        List of detected PII type names (empty if none found)
    """
    detected = []

    for pattern, pii_type in _COMPILED_PATTERNS:
        if pattern.search(text):
            detected.append(pii_type)

    return detected
