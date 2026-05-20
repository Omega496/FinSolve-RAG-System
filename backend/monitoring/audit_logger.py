"""
Structured JSON audit log writer.

Writes security-relevant events to append-only JSONL file.
Each line is a complete JSON object for easy parsing.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Configuration ─────────────────────────────────────────────────────
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "./logs/audit.jsonl")


def _ensure_log_dir() -> None:
    """Create log directory if it doesn't exist."""
    Path(AUDIT_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)


def log_event(
    event_type: str,
    user_id: str,
    session_id: str,
    role: str,
    details: Optional[dict] = None,
) -> None:
    """
    Write a structured audit event to JSONL log.

    Args:
        event_type: Event category (login, query, rbac_route, guardrail_block, etc.)
        user_id: Employee ID from JWT
        session_id: Session UUID
        role: User's RBAC role
        details: Additional event-specific data
    """
    _ensure_log_dir()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "details": details or {},
    }

    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_rbac_route(
    user_id: str,
    session_id: str,
    role: str,
    filter_summary: dict,
) -> None:
    """
    Log RBAC routing decision.

    Args:
        user_id: Employee ID
        session_id: Session UUID
        role: User's RBAC role
        filter_summary: Summary of applied filter (not full filter — avoid log bloat)
    """
    log_event(
        event_type="rbac_route",
        user_id=user_id,
        session_id=session_id,
        role=role,
        details={"filter_summary": filter_summary},
    )


def log_guardrail_block(
    user_id: str,
    session_id: str,
    role: str,
    block_reason: str,
    query_preview: str,
) -> None:
    """
    Log guardrail block event.

    Args:
        user_id: Employee ID
        session_id: Session UUID
        role: User's RBAC role
        block_reason: Why blocked (off_topic, prompt_injection, unauthorized, pii_detected)
        query_preview: First 100 chars of blocked query
    """
    log_event(
        event_type="guardrail_block",
        user_id=user_id,
        session_id=session_id,
        role=role,
        details={
            "block_reason": block_reason,
            "query_preview": query_preview[:100],
        },
    )


def log_query(
    user_id: str,
    session_id: str,
    role: str,
    query: str,
    chunks_retrieved: int,
    latency_ms: float,
) -> None:
    """
    Log completed query with metrics.

    Args:
        user_id: Employee ID
        session_id: Session UUID
        role: User's RBAC role
        query: User's query text
        chunks_retrieved: Number of chunks returned
        latency_ms: End-to-end latency
    """
    log_event(
        event_type="query",
        user_id=user_id,
        session_id=session_id,
        role=role,
        details={
            "query_preview": query[:100],
            "chunks_retrieved": chunks_retrieved,
            "latency_ms": latency_ms,
        },
    )


# ─── Log Reading Functions ─────────────────────────────────────────────

def read_logs(limit: int = 100) -> list[dict]:
    """
    Read last N audit log entries.

    Args:
        limit: Maximum entries to return (default 100)

    Returns:
        List of log entry dicts, most recent first
    """
    if not Path(AUDIT_LOG_PATH).exists():
        return []

    entries = []
    with open(AUDIT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Return most recent first
    return entries[-limit:][::-1]


def read_guardrail_events(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> list[dict]:
    """
    Read guardrail block events filtered by date range.

    Args:
        start_date: Filter events after this date (inclusive)
        end_date: Filter events before this date (inclusive)

    Returns:
        List of guardrail event dicts, most recent first
    """
    if not Path(AUDIT_LOG_PATH).exists():
        return []

    entries = []
    with open(AUDIT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter by event type
            if entry.get("event_type") not in ("guardrail_block", "pii_detected"):
                continue

            # Filter by date range
            timestamp_str = entry.get("timestamp", "")
            if timestamp_str:
                try:
                    entry_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if start_date and entry_time < start_date:
                        continue
                    if end_date and entry_time > end_date:
                        continue
                except ValueError:
                    continue

            entries.append(entry)

    # Return most recent first
    return entries[::-1]
