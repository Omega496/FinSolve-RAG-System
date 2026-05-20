"""
LangGraph node — LLM generation.

Calls Nemotron via Ollama with retrieval-anchoring prompt.
Supports streaming via .astream().
Never modifies system prompt — uses verbatim from AGNNTS.md.

Error handling:
    - 30 second timeout for Ollama inference
    - Catches all exceptions, sets blocked state
    - Never exposes internal errors to client
"""

import asyncio
import logging
import os
from typing import AsyncGenerator

from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage, SystemMessage

from backend.graph.state import RAGState
from backend.monitoring.audit_logger import log_event

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nemotron-3-super:cloud")
INFERENCE_TIMEOUT = 30  # seconds

# ─── System Prompt (verbatim from AGNNTS.md — NEVER modify) ───────────
SYSTEM_PROMPT = """You are FinSolve's internal enterprise assistant. You help employees query company documents.

STRICT RULES:
1. Answer ONLY using the provided context below. 
2. If the answer is not explicitly in the context, respond: "I don't have enough information in the available documents to answer this."
3. NEVER infer, speculate, extrapolate, or use outside knowledge.
4. NEVER reveal information about documents the user is not authorized to access.
5. If asked about other employees' personal data (salaries, performance reviews, personal details), refuse unless the user is HR or C-Suite.
6. Always cite which document section your answer comes from.

Context:
{retrieved_context}

Conversation History:
{conversation_history}"""

# ─── Singleton LLM ────────────────────────────────────────────────────
_llm: Ollama | None = None


def _get_llm() -> Ollama:
    """Get or create singleton Ollama LLM instance."""
    global _llm

    if _llm is None:
        _llm = Ollama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_MODEL,
            temperature=0.1,
        )

    return _llm


async def generator(state: RAGState) -> RAGState:
    """
    LangGraph node — generate LLM response.

    Steps:
        1. Build context string from parent_chunks
        2. Build conversation history string (last 5 turns)
        3. Inject into system prompt (verbatim from AGNNTS.md)
        4. Call Nemotron via Ollama with timeout
        5. Stream tokens to state["streamed_tokens"]
        6. Store complete response in state["response"]

    Error handling:
        - Timeout after 30 seconds
        - Catch all exceptions
        - Set blocked state on error
        - Never expose internal errors
    """
    try:
        parent_chunks = state.get("parent_chunks", [])
        conversation_history = state.get("conversation_history", [])

        # ── Step 1: Build context string from parent chunks ────────
        context_str = _build_context(parent_chunks)

        # ── Step 2: Build conversation history string ──────────────
        history_str = _build_history(conversation_history)

        # ── Step 3: Inject into system prompt (verbatim) ───────────
        system_message = SYSTEM_PROMPT.format(
            retrieved_context=context_str,
            conversation_history=history_str,
        )

        # ── Step 4: Build user message ─────────────────────────────
        user_message = state["query"]

        # ── Step 5: Call LLM with streaming and timeout ────────────
        llm = _get_llm()
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        streamed_tokens = []
        full_response = ""

        # Stream with timeout
        try:
            async with asyncio.timeout(INFERENCE_TIMEOUT):
                async for chunk in llm.astream(messages):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    streamed_tokens.append(token)
                    full_response += token
        except asyncio.TimeoutError:
            logger.error(f"Ollama inference timeout after {INFERENCE_TIMEOUT}s")
            state["blocked"] = True
            state["block_reason"] = "inference_timeout"
            state["response"] = "I apologize, but the response took too long. Please try a simpler query."
            state["streamed_tokens"] = [state["response"]]
            log_event(
                event_type="inference_timeout",
                user_id=state.get("user_id", "unknown"),
                session_id=state.get("session_id", ""),
                role=state.get("role", ""),
                details={"timeout_seconds": INFERENCE_TIMEOUT},
            )
            return state

        # ── Step 6: Store in state ─────────────────────────────────
        state["response"] = full_response
        state["streamed_tokens"] = streamed_tokens

        return state

    except Exception as e:
        # ── Graceful failure ───────────────────────────────────────
        logger.error(f"Generator error: {e}")
        log_event(
            event_type="generator_error",
            user_id=state.get("user_id", "unknown"),
            session_id=state.get("session_id", ""),
            role=state.get("role", ""),
            details={"error": str(e)[:200]},
        )
        state["blocked"] = True
        state["block_reason"] = "generation_error"
        state["response"] = "I apologize, but I encountered an error generating a response. Please try again."
        state["streamed_tokens"] = [state["response"]]
        return state


def _build_context(chunks: list[dict]) -> str:
    """Build context string from parent chunks for system prompt."""
    if not chunks:
        return "No relevant documents found."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("text", "")
        breadcrumb = chunk.get("header_breadcrumb", "")
        source = chunk.get("source_file", "")
        part = f"[{source}] {breadcrumb}\n{text}"
        context_parts.append(part)

    return "\n\n---\n\n".join(context_parts)


def _build_history(history: list[dict]) -> str:
    """Build conversation history string from last 5 turns."""
    if not history:
        return "No conversation history."

    recent = history[-5:]

    lines = []
    for turn in recent:
        user_msg = turn.get("user", "")
        assistant_msg = turn.get("assistant", "")

        if user_msg:
            lines.append(f"User: {user_msg}")
        if assistant_msg:
            lines.append(f"Assistant: {assistant_msg}")

    return "\n".join(lines) if lines else "No conversation history."
