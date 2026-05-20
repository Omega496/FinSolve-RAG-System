"""
LangGraph pipeline — complete RAG graph definition and compilation.

Assembles all 7 nodes with conditional routing:
    input_guardrail → rbac_router → retriever → parent_child_swap
    → generator → output_scanner → memory_update → END

Conditional edges:
    - input_guardrail blocked → END
    - retriever blocked → END (no relevant documents)
    - output_scanner blocked → END (PII detected)
"""

import os

from langgraph.graph import StateGraph, END
from langsmith import Client as LangSmithClient

from backend.graph.state import RAGState
from backend.graph.nodes.input_guardrail import input_guardrail
from backend.graph.nodes.rbac_router import rbac_router
from backend.graph.nodes.retriever import retriever
from backend.graph.nodes.parent_child_swap import parent_child_swap_node
from backend.graph.nodes.generator import generator
from backend.graph.nodes.output_scanner import output_scanner
from backend.graph.nodes.memory_update import memory_update

# ─── Configuration ─────────────────────────────────────────────────────
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "finsolve-rag")


def _setup_langsmith() -> None:
    """
    Configure LangSmith tracing if enabled.
    Sets environment variables for LangChain callback integration.
    """
    if LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT
    else:
        # Ensure tracing is disabled if not configured
        os.environ.pop("LANGCHAIN_TRACING_V2", None)


def _should_continue_after_guardrail(state: RAGState) -> str:
    """
    Route after input guardrail check.

    Returns:
        "rbac_router" if not blocked, "end" if blocked
    """
    if state.get("blocked", False):
        return "end"
    return "rbac_router"


def _should_continue_after_retrieval(state: RAGState) -> str:
    """
    Route after retrieval.

    Returns:
        "parent_child_swap" if not blocked, "end" if blocked
    """
    if state.get("blocked", False):
        return "end"
    return "parent_child_swap"


def _should_continue_after_output_scan(state: RAGState) -> str:
    """
    Route after output scan.

    Returns:
        "memory_update" if not blocked, "end" if blocked
    """
    if state.get("blocked", False):
        return "end"
    return "memory_update"


def build_pipeline() -> StateGraph:
    """
    Build and compile the complete RAG pipeline.

    Nodes (in order):
        1. input_guardrail — check query against guardrails
        2. rbac_router — build RBAC payload filter
        3. retriever — hybrid dense+sparse retrieval
        4. parent_child_swap — fetch parent chunks
        5. generator — LLM response generation
        6. output_scanner — PII detection
        7. memory_update — sliding window memory

    Conditional edges:
        - input_guardrail blocked → END
        - retriever blocked → END
        - output_scanner blocked → END

    Returns:
        Compiled StateGraph ready for invocation
    """
    # ── Setup LangSmith tracing ────────────────────────────────────
    _setup_langsmith()

    # ── Create graph ───────────────────────────────────────────────
    workflow = StateGraph(RAGState)

    # ── Add nodes ──────────────────────────────────────────────────
    workflow.add_node("input_guardrail", input_guardrail)
    workflow.add_node("rbac_router", rbac_router)
    workflow.add_node("retriever", retriever)
    workflow.add_node("parent_child_swap", parent_child_swap_node)
    workflow.add_node("generator", generator)
    workflow.add_node("output_scanner", output_scanner)
    workflow.add_node("memory_update", memory_update)

    # ── Set entry point ────────────────────────────────────────────
    workflow.set_entry_point("input_guardrail")

    # ── Add conditional edges ──────────────────────────────────────
    workflow.add_conditional_edges(
        "input_guardrail",
        _should_continue_after_guardrail,
        {
            "rbac_router": "rbac_router",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "retriever",
        _should_continue_after_retrieval,
        {
            "parent_child_swap": "parent_child_swap",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "output_scanner",
        _should_continue_after_output_scan,
        {
            "memory_update": "memory_update",
            "end": END,
        },
    )

    # ── Add linear edges (no branching) ────────────────────────────
    workflow.add_edge("rbac_router", "retriever")
    workflow.add_edge("parent_child_swap", "generator")
    workflow.add_edge("generator", "output_scanner")
    workflow.add_edge("memory_update", END)

    # ── Compile ────────────────────────────────────────────────────
    return workflow.compile()


# ─── Compiled pipeline instance (singleton) ────────────────────────────
pipeline = build_pipeline()
