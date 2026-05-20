"""
Hybrid retriever — dense + sparse + Reciprocal Rank Fusion (RRF).

Retrieves child chunks from Qdrant using both semantic (dense) and
keyword (sparse/BM25) search, then merges results with weighted RRF.

Configuration (from AGNNTS.md):
    DENSE_WEIGHT = 0.7
    SPARSE_WEIGHT = 0.3
    TOP_K_RETRIEVAL = 10
    TOP_K_FINAL = 5
    RRF_K = 60
"""

from dataclasses import dataclass, field

from qdrant_client.models import QueryResponse, SparseVector, Filter, FieldCondition, MatchValue

from backend.ingestion.embedder import encode_both
from backend.retrieval.qdrant_client import get_qdrant_client, QDRANT_COLLECTION
from backend.retrieval.rbac_filter import build_rbac_filter

# ─── Retrieval Configuration ──────────────────────────────────────────
DENSE_WEIGHT = 0.7
SPARSE_WEIGHT = 0.3
TOP_K_RETRIEVAL = 10   # Per retrieval method
TOP_K_FINAL = 5        # After RRF merge
RRF_K = 60             # RRF constant


@dataclass
class RetrievedChunk:
    """A retrieved chunk with score and full metadata."""
    id: str
    score: float
    payload: dict = field(repr=False)

    @property
    def text(self) -> str:
        """Chunk text content."""
        return self.payload.get("text", "")

    @property
    def doc_id(self) -> str:
        """Document identifier."""
        return self.payload.get("doc_id", "")

    @property
    def header_breadcrumb(self) -> str:
        """Section header path."""
        return self.payload.get("header_breadcrumb", "")

    @property
    def source_file(self) -> str:
        """Original source filename."""
        return self.payload.get("source_file", "")

    @property
    def parent_id(self) -> str | None:
        """Parent chunk ID, or None if atomic."""
        return self.payload.get("parent_id")

    @property
    def is_atomic(self) -> bool:
        """True if chunk has no parent (atomic or top-level)."""
        return self.parent_id is None


@dataclass
class ParentSwapResult:
    """Result of parent-child swap.

    parent_chunks: Parent chunks for LLM context (richer, ~400 tokens).
    child_chunks: Original child chunks for source citations.
    """
    parent_chunks: list[RetrievedChunk] = field(default_factory=list)
    child_chunks: list[RetrievedChunk] = field(default_factory=list)


def hybrid_retrieve(query: str, role: str) -> list[RetrievedChunk]:
    """
    Retrieve child chunks using hybrid dense + sparse search with RRF.

    Pipeline:
        1. Encode query with BGE-M3 (dense + sparse)
        2. Query Qdrant with dense vector (TOP_K=10) + RBAC filter
        3. Query Qdrant with sparse vector (TOP_K=10) + same RBAC filter
        4. Merge results using weighted RRF (k=60, dense=0.7, sparse=0.3)
        5. Return top 5 deduplicated child chunks with full metadata

    Args:
        query: User's natural language query text
        role: Authenticated user's role (from JWT, server-side only)

    Returns:
        List of RetrievedChunk objects sorted by RRF score (descending).
        Each chunk includes full payload metadata.
    """
    # ── Step 1: Encode query ───────────────────────────────────────
    vectors = encode_both([query])
    dense_vector = vectors[0]["dense"]
    sparse_data = vectors[0]["sparse"]

    # Convert sparse dict to Qdrant SparseVector format
    sparse_vector = SparseVector(
        indices=list(sparse_data.keys()),
        values=list(sparse_data.values()),
    )

    # ── Step 2: Build RBAC filter (server-side, immutable) ─────────
    rbac_filter = build_rbac_filter(role)

    client = get_qdrant_client()

    # ── Step 3: Dense retrieval ────────────────────────────────────
    dense_results: QueryResponse = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=dense_vector,
        using="dense",
        limit=TOP_K_RETRIEVAL,
        query_filter=rbac_filter,
    )

    # ── Step 4: Sparse retrieval ───────────────────────────────────
    sparse_results: QueryResponse = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=sparse_vector,
        using="bm25",
        limit=TOP_K_RETRIEVAL,
        query_filter=rbac_filter,
    )

    # ── Step 5: Merge with RRF ─────────────────────────────────────
    rrf_scores: dict[str, float] = {}
    chunk_data: dict[str, dict] = {}

    # Process dense results
    for rank, point in enumerate(dense_results.points):
        point_id = str(point.id)
        rrf_scores[point_id] = rrf_scores.get(point_id, 0.0) + (
            DENSE_WEIGHT / (RRF_K + rank)
        )
        chunk_data[point_id] = {
            "id": point_id,
            "payload": point.payload,
        }

    # Process sparse results
    for rank, point in enumerate(sparse_results.points):
        point_id = str(point.id)
        rrf_scores[point_id] = rrf_scores.get(point_id, 0.0) + (
            SPARSE_WEIGHT / (RRF_K + rank)
        )
        if point_id not in chunk_data:
            chunk_data[point_id] = {
                "id": point_id,
                "payload": point.payload,
            }

    # ── Step 6: Sort by RRF score, return top K ────────────────────
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for point_id in sorted_ids[:TOP_K_FINAL]:
        data = chunk_data[point_id]
        results.append(RetrievedChunk(
            id=point_id,
            score=rrf_scores[point_id],
            payload=data["payload"],
        ))

    return results


def parent_child_swap(child_chunks: list[RetrievedChunk]) -> ParentSwapResult:
    """
    Swap child chunks for their parent chunks.

    Parent chunks provide richer context (~400 tokens) for LLM generation.
    Child chunks retained for source citations (more specific).

    Logic:
        1. Extract parent_id from each child
        2. Atomic chunks (no parent) used as-is
        3. Fetch parents from Qdrant by ID
        4. Deduplicate if multiple children share parent
        5. Return both: parents for LLM, children for citations

    Args:
        child_chunks: Top-5 child chunks from hybrid_retrieve()

    Returns:
        ParentSwapResult with parent_chunks (for LLM) and child_chunks (for citations)
    """
    if not child_chunks:
        return ParentSwapResult()

    # ── Step 1: Separate atomic vs child chunks ────────────────────
    atomic_chunks: list[RetrievedChunk] = []
    children_with_parent: list[RetrievedChunk] = []
    parent_ids_needed: set[str] = set()

    for chunk in child_chunks:
        if chunk.is_atomic:
            atomic_chunks.append(chunk)
        else:
            children_with_parent.append(chunk)
            parent_ids_needed.add(chunk.parent_id)

    # ── Step 2: Fetch parent chunks from Qdrant ────────────────────
    parent_map: dict[str, RetrievedChunk] = {}

    if parent_ids_needed:
        client = get_qdrant_client()
        parent_points = client.retrieve(
            collection_name=QDRANT_COLLECTION,
            ids=list(parent_ids_needed),
            with_payload=True,
        )

        for point in parent_points:
            point_id = str(point.id)
            parent_map[point_id] = RetrievedChunk(
                id=point_id,
                score=0.0,  # Parents not scored — context only
                payload=point.payload,
            )

    # ── Step 3: Build parent list, deduplicated ────────────────────
    # Multiple children may share same parent — deduplicate by ID
    seen_parent_ids: set[str] = set()
    parent_chunks: list[RetrievedChunk] = []

    # Add atomic chunks as-is (they ARE their own parent)
    parent_chunks.extend(atomic_chunks)

    # Add fetched parents in order of first child appearance
    for child in children_with_parent:
        pid = child.parent_id
        if pid not in seen_parent_ids:
            seen_parent_ids.add(pid)
            if pid in parent_map:
                parent_chunks.append(parent_map[pid])
            else:
                # Parent not found — fallback to child
                parent_chunks.append(child)

    return ParentSwapResult(
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
    )
