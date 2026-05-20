"""
FinSolve RAG System — FastAPI Application Entry Point
"""

import asyncio
import json
import os
import time
import traceback
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth.dependencies import get_current_user
from .auth.jwt_handler import COOKIE_NAME, create_jwt, set_jwt_cookie
from .graph.state import RAGState, create_initial_state
from .graph.pipeline import pipeline
from .monitoring.audit_logger import log_query, log_guardrail_block, read_logs, read_guardrail_events
from .monitoring.ragas_evaluator import trigger_async_evaluation

# ─── Test Users (Local Development Only) ───────────────────────────────
TEST_USERS = {
    "alice@finsolve.com": {
        "password": "test123",
        "role": "engineering",
        "department": "engineering",
        "name": "Alice",
    },
    "bob@finsolve.com": {
        "password": "test123",
        "role": "finance",
        "department": "finance",
        "name": "Bob",
    },
    "carol@finsolve.com": {
        "password": "test123",
        "role": "marketing",
        "department": "marketing",
        "name": "Carol",
    },
    "dave@finsolve.com": {
        "password": "test123",
        "role": "hr",
        "department": "hr",
        "name": "Dave",
    },
    "eve@finsolve.com": {
        "password": "test123",
        "role": "c_suite",
        "department": "c_suite",
        "name": "Eve",
    },
    "frank@finsolve.com": {
        "password": "test123",
        "role": "employee",
        "department": "employee",
        "name": "Frank",
    },
}

# ─── FastAPI App ───────────────────────────────────────────────────────
app = FastAPI(
    title="FinSolve RAG System",
    description="Internal enterprise chatbot with RBAC-enforced document retrieval",
    version="1.0.0",
)

# ─── CORS Middleware (from AGENTS.md) ──────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,  # Required for httpOnly cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ───────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    name: str
    role: str


class UserResponse(BaseModel):
    name: str
    role: str
    session_id: str


class QueryRequest(BaseModel):
    query: str
    session_id: str


# ─── Auth Routes ───────────────────────────────────────────────────────
@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """
    Authenticate user, create JWT, set httpOnly cookie.
    Returns user name and role — never the token in response body.
    """
    user = TEST_USERS.get(request.email)

    if not user or user["password"] != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_jwt(
        employee_id=request.email,
        role=user["role"],
        department=user["department"],
        name=user["name"],
    )

    set_jwt_cookie(response, token)

    return LoginResponse(name=user["name"], role=user["role"])


@app.post("/auth/logout")
async def logout(response: Response):
    """Clear the httpOnly authentication cookie."""
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=False,  # Match COOKIE_SECURE setting
        samesite="strict",
    )
    return {"message": "Logged out successfully"}


@app.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Protected route — returns current user's name, role, and session_id."""
    return UserResponse(
        name=user["name"],
        role=user["role"],
        session_id=user["session_id"],
    )


# ─── Query Endpoint ────────────────────────────────────────────────────
@app.post("/query")
async def query_endpoint(
    request: QueryRequest,
    user: dict = Depends(get_current_user),
):
    """
    Protected RAG query endpoint with SSE streaming.

    Auth:
        JWT from httpOnly cookie via get_current_user() dependency.
        Role, session_id, user_id extracted server-side from verified JWT.
        NEVER from request body.

    Returns:
        StreamingResponse with SSE events:
            - {"type": "token", "content": "..."} — streamed tokens
            - {"type": "sources", "content": [...]} — source citations
            - {"type": "blocked", "reason": "..."} — if blocked
            - {"type": "done"} — on completion
    """
    # ── Extract from JWT (server-side, never from body) ────────────
    role = user["role"]
    user_id = user["sub"]  # employee_id
    session_id = request.session_id  # Client provides session_id for grouping
    query = request.query

    # ── Validate session_id format (basic check) ───────────────────
    if not session_id or len(session_id) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id",
        )

    # ── Build initial state ────────────────────────────────────────
    # Use conversation history from session if available (placeholder)
    history = []  # TODO: Load from session store if needed

    initial_state = create_initial_state(
        query=query,
        role=role,
        session_id=session_id,
        user_id=user_id,
        history=history,
    )

    # ── Stream pipeline ────────────────────────────────────────────
    async def event_generator():
        start_time = time.monotonic()
        final_state = None

        try:
            async for event in pipeline.astream(initial_state):
                # Each event is a dict with node name as key
                for node_name, node_output in event.items():
                    if node_output is None:
                        continue

                    # ── Stream tokens from generator ───────────────
                    if node_name == "generator" and "streamed_tokens" in node_output:
                        tokens = node_output.get("streamed_tokens", [])
                        for token in tokens:
                            yield _sse_event("token", token)

                    # ── Handle blocked state ───────────────────────
                    if node_output.get("blocked", False):
                        block_reason = node_output.get("block_reason", "unknown")
                        yield _sse_event("blocked", block_reason)
                        final_state = node_output
                        break

                    # ── Capture final state ────────────────────────
                    if node_name == "memory_update":
                        final_state = node_output

                # If blocked, stop processing
                if final_state and final_state.get("blocked", False):
                    break

            # ── Send source citations ──────────────────────────────
            if final_state and not final_state.get("blocked", False):
                sources = _extract_sources(final_state)
                if sources:
                    yield _sse_event("sources", sources)

            # ── Send done event ────────────────────────────────────
            yield _sse_event("done", None)

            # ── Trigger async evaluation + logging (non-blocking) ──
            _trigger_post_processing(
                query=query,
                response=final_state.get("response", "") if final_state else "",
                state=final_state,
                start_time=start_time,
                role=role,
                user_id=user_id,
                session_id=session_id,
            )

        except Exception as e:
            # ── Graceful error handling ────────────────────────────
            # Log full traceback server-side
            traceback.print_exc()

            # Send generic error to client (never expose internals)
            yield _sse_event("error", "An internal error occurred. Please try again.")
            yield _sse_event("done", None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def _sse_event(event_type: str, content) -> str:
    """
    Format SSE event.

    Args:
        event_type: "token", "sources", "blocked", "done", "error"
        content: Event payload (string, list, or None)

    Returns:
        Formatted SSE string
    """
    data = {"type": event_type, "content": content}
    return f"data: {json.dumps(data)}\n\n"


def _extract_sources(state: RAGState) -> list[dict]:
    """
    Extract source citations from child chunks.

    Returns:
        List of source dicts with doc_id, header, source_file
    """
    sources = []
    seen = set()

    for chunk in state.get("retrieved_chunks", []):
        source_key = f"{chunk.get('doc_id', '')}:{chunk.get('header_breadcrumb', '')}"
        if source_key not in seen:
            seen.add(source_key)
            sources.append({
                "doc_id": chunk.get("doc_id", ""),
                "header": chunk.get("header_breadcrumb", ""),
                "source_file": chunk.get("source_file", ""),
            })

    return sources


def _trigger_post_processing(
    query: str,
    response: str,
    state: RAGState | None,
    start_time: float,
    role: str,
    user_id: str,
    session_id: str,
) -> None:
    """
    Trigger async RAGAS evaluation and audit logging.
    Non-blocking — does not affect response streaming.
    """
    latency_ms = (time.monotonic() - start_time) * 1000

    # ── Audit log ──────────────────────────────────────────────────
    chunks_retrieved = len(state.get("retrieved_chunks", [])) if state else 0
    log_query(
        user_id=user_id,
        session_id=session_id,
        role=role,
        query=query,
        chunks_retrieved=chunks_retrieved,
        latency_ms=latency_ms,
    )

    # ── RAGAS evaluation (fire-and-forget) ─────────────────────────
    trigger_async_evaluation(
        query=query,
        response=response,
        retrieved_chunks=state.get("retrieved_chunks", []) if state else [],
        session_id=session_id,
        user_id=user_id,
        role=role,
        blocked=state.get("blocked", False) if state else True,
    )


# ─── Health Check ──────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """
    Public health check endpoint.
    Tests connections to Qdrant and Ollama.
    Returns degraded status if any dependency is unhealthy.
    """
    health = {
        "service": "finsolve-backend",
        "status": "healthy",
        "dependencies": {},
    }

    # ── Check Qdrant connection ────────────────────────────────────
    try:
        from .retrieval.qdrant_client import get_qdrant_client
        client = get_qdrant_client()
        collections = client.get_collections()
        health["dependencies"]["qdrant"] = {
            "status": "healthy",
            "collections": len(collections.collections),
        }
    except Exception as e:
        health["dependencies"]["qdrant"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # ── Check Ollama connection ────────────────────────────────────
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                health["dependencies"]["ollama"] = {
                    "status": "healthy",
                    "models_available": len(models),
                }
            else:
                health["dependencies"]["ollama"] = {
                    "status": "unhealthy",
                    "error": f"HTTP {resp.status_code}",
                }
                health["status"] = "degraded"
    except Exception as e:
        health["dependencies"]["ollama"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    return health


# ─── Audit Log Routes (C-Suite Only) ───────────────────────────────────
@app.get("/audit/logs")
async def get_audit_logs(user: dict = Depends(get_current_user)):
    """
    Protected route — C-Suite only.
    Returns last 100 audit log entries.
    Role check is server-side from verified JWT.
    """
    # ── Server-side role check (never trust client) ────────────────
    if user["role"] != "c_suite":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. C-Suite role required.",
        )

    logs = read_logs(limit=100)
    return {"logs": logs, "count": len(logs)}


@app.get("/audit/guardrail-events")
async def get_guardrail_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """
    Protected route — C-Suite only.
    Returns guardrail trigger events filtered by date range.
    Query params: start_date, end_date (ISO 8601 format)
    Role check is server-side from verified JWT.
    """
    # ── Server-side role check (never trust client) ────────────────
    if user["role"] != "c_suite":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. C-Suite role required.",
        )

    # ── Parse date filters ─────────────────────────────────────────
    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601.",
            )

    if end_date:
        try:
            parsed_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601.",
            )

    events = read_guardrail_events(
        start_date=parsed_start,
        end_date=parsed_end,
    )

    return {
        "events": events,
        "count": len(events),
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }
