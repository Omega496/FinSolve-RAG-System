"""
LangGraph node — input guardrail check.

Runs NeMo Guardrails on incoming query:
    - Off-topic rail: blocks non-company queries
    - Prompt injection rail: blocks injection attempts
    - Role boundary rail: blocks unauthorized employee data requests

Never modifies query. Only sets blocked/block_reason in state.
Graceful degradation if NeMo fails — falls back to regex-only guardrails.
"""

import logging
import os
import re
from pathlib import Path

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────
NEMO_CONFIG_PATH = os.getenv(
    "NEMO_CONFIG_PATH",
    str(Path(__file__).parent.parent.parent / "guardrails" / "nemo_config"),
)

# ─── NeMo Availability ────────────────────────────────────────────────
_NEMO_AVAILABLE = False
_rails = None
_nemo_init_error = None

try:
    from nemoguardrails import LLMRails, RailsConfig
    _NEMO_AVAILABLE = True
except ImportError as e:
    _nemo_init_error = f"NeMo import failed: {e}"
    logger.warning(_nemo_init_error)
except Exception as e:
    _nemo_init_error = f"NeMo init error: {e}"
    logger.warning(_nemo_init_error)

# ─── Regex Fallback Patterns ───────────────────────────────────────────
OFF_TOPIC_PATTERNS = [
    r"\b(write|tell|sing)\s+(me\s+)?(a\s+)?(poem|song|joke|story)\b",
    r"\b(weather|forecast|temperature)\b.*\b(today|tomorrow|outside)\b",
    r"\b(what\s+time|current\s+time|clock)\b",
    r"\b(how\s+are\s+you|your\s+name|who\s+made\s+you)\b",
]

INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)\b",
    r"\bforget\s+(your|all)\s+(instructions|prompts|rules|system)\b",
    r"\byou\s+are\s+now\b",
    r"\bpretend\s+(you\s+are|to\s+be)\b",
    r"\bact\s+as\s+if\b",
    r"\bdisregard\s+(all|previous|your)\b",
    r"\boverride\s+(your|the)\s+(instructions|rules)\b",
    r"\bnew\s+instructions\s*:\s*\b",
    r"\bsystem\s*:\s*you\s+are\b",
]

_COMPILED_OFF_TOPIC = [re.compile(p, re.IGNORECASE) for p in OFF_TOPIC_PATTERNS]
_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def _get_rails():
    """
    Get or create singleton NeMo Guardrails instance.
    Returns None if NeMo unavailable — falls back to regex.
    """
    global _rails, _NEMO_AVAILABLE

    if not _NEMO_AVAILABLE:
        return None

    if _rails is None:
        try:
            config = RailsConfig.from_path(NEMO_CONFIG_PATH)
            _rails = LLMRails(config)
        except Exception as e:
            _NEMO_AVAILABLE = False
            logger.error(f"NeMo Guardrails failed to initialize: {e}")
            log_event(
                event_type="nemo_init_failed",
                user_id="system",
                session_id="",
                role="system",
                details={"error": str(e)},
            )

    return _rails


async def input_guardrail(state: RAGState) -> RAGState:
    """
    LangGraph node — check query against input guardrails.

    Rails checked:
        1. off_topic: non-company queries (weather, jokes, etc.)
        2. prompt_injection: injection attempts (ignore instructions, etc.)
        3. unauthorized: employee data boundary violations

    If any rail fires:
        state["blocked"] = True
        state["block_reason"] = specific reason
        state["guardrail_triggered"] = True

    If all rails pass:
        state["blocked"] = False

    Query is NEVER modified.

    Graceful degradation:
        - If NeMo fails → falls back to regex-only guardrails
        - If any error → fail-open (don't block legitimate queries)
    """
    query = state["query"]
    role = state["role"]

    try:
        # ── Check off-topic ────────────────────────────────────────
        is_off_topic = await _check_off_topic(query)
        if is_off_topic:
            state["blocked"] = True
            state["block_reason"] = "off_topic"
            state["guardrail_triggered"] = True
            return state

        # ── Check prompt injection ─────────────────────────────────
        is_injection = await _check_prompt_injection(query)
        if is_injection:
            state["blocked"] = True
            state["block_reason"] = "prompt_injection"
            state["guardrail_triggered"] = True
            return state

        # ── Check role boundary (employee data requests) ───────────
        is_boundary_violation = await _check_role_boundary(query, role)
        if is_boundary_violation:
            state["blocked"] = True
            state["block_reason"] = "unauthorized"
            state["guardrail_triggered"] = True
            return state

        # ── All rails passed ───────────────────────────────────────
        state["blocked"] = False
        state["block_reason"] = None
        state["guardrail_triggered"] = False
        return state

    except Exception as e:
        # ── Graceful failure — fail open ───────────────────────────
        logger.error(f"Input guardrail error: {e}")
        log_event(
            event_type="guardrail_error",
            user_id=state.get("user_id", "unknown"),
            session_id=state.get("session_id", ""),
            role=role,
            details={"error": str(e)[:200]},
        )
        # Fail open — don't block legitimate queries due to guardrail failure
        state["blocked"] = False
        state["block_reason"] = None
        state["guardrail_triggered"] = False
        return state


async def _check_off_topic(query: str) -> bool:
    """
    Check if query is off-topic (not about company documents).
    Uses NeMo if available, falls back to regex.
    """
    # ── Try NeMo first ─────────────────────────────────────────────
    rails = _get_rails()
    if rails:
        try:
            result = rails.generate(
                messages=[{"role": "user", "content": query}],
            )
            response = result if isinstance(result, str) else result.get("content", "")
            return "internal document assistant" in response.lower()
        except Exception as e:
            logger.warning(f"NeMo off-topic check failed, using regex: {e}")

    # ── Regex fallback ─────────────────────────────────────────────
    return any(pattern.search(query) for pattern in _COMPILED_OFF_TOPIC)


async def _check_prompt_injection(query: str) -> bool:
    """
    Check if query contains prompt injection attempt.
    Uses NeMo if available, falls back to regex.
    """
    # ── Try NeMo first ─────────────────────────────────────────────
    rails = _get_rails()
    if rails:
        try:
            result = rails.generate(
                messages=[{"role": "user", "content": query}],
            )
            response = result if isinstance(result, str) else result.get("content", "")
            return "cannot process that request" in response.lower()
        except Exception as e:
            logger.warning(f"NeMo injection check failed, using regex: {e}")

    # ── Regex fallback ─────────────────────────────────────────────
    return any(pattern.search(query) for pattern in _COMPILED_INJECTION)


async def _check_role_boundary(query: str, role: str) -> bool:
    """
    Check if query requests other employees' personal data.

    HR and C-Suite roles can access employee data.
    Other roles trigger boundary violation.
    """
    # HR and C-Suite can request employee data
    if role in ("hr", "c_suite"):
        return False

    # Keywords indicating employee data request
    employee_data_keywords = [
        "salary", "salaries", "pay", "compensation",
        "performance review", "review rating",
        "personal details", "address", "phone number",
        "bank account", "ssn", "social security",
    ]

    query_lower = query.lower()
    has_employee_keyword = any(kw in query_lower for kw in employee_data_keywords)

    if not has_employee_keyword:
        return False

    # Check if asking about specific person (not self)
    personal_query_pattern = r"(?:what|show|tell|get|give)\s+(?:me\s+)?(?:is\s+)?(?:the\s+)?(?:\w+\s+)?(?:'s|their|his|her)\s+"
    if re.search(personal_query_pattern, query_lower):
        return has_employee_keyword

    return False
