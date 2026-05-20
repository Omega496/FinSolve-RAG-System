"""
Qdrant connection + collection setup.
Supports hybrid retrieval (dense + sparse vectors) for BGE-M3 + BM25.
"""

import os
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    VectorParams,
    SparseVectorParams,
    VectorsConfig,
    SparseVectorsConfig,
)

# ─── Environment Variables ────────────────────────────────────────────
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "finsolve_chunks")

# ─── BGE-M3 Configuration ─────────────────────────────────────────────
DENSE_VECTOR_DIM = 1024  # BGE-M3 output dimensions
DENSE_DISTANCE = Distance.COSINE

# ─── Singleton Client ─────────────────────────────────────────────────
_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create a singleton Qdrant client connection.

    Returns:
        Connected QdrantClient instance
    """
    global _client

    if _client is None:
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    return _client


def initialize_collection() -> None:
    """
    Create the finsolve_chunks collection if it doesn't exist.
    Configures:
        - Dense vectors: 1024 dimensions, cosine distance (BGE-M3)
        - Sparse vectors: enabled (BM25 hybrid retrieval)
        - Payload indexes for metadata filtering
    """
    client = get_qdrant_client()

    # Check if collection exists
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if QDRANT_COLLECTION not in collection_names:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorsConfig(
                dense=VectorParams(
                    size=DENSE_VECTOR_DIM,
                    distance=DENSE_DISTANCE,
                )
            ),
            sparse_vectors_config=SparseVectorsConfig(
                sparse={
                    "bm25": SparseVectorParams(),
                }
            ),
        )
        print(f"Created collection: {QDRANT_COLLECTION}")
    else:
        print(f"Collection already exists: {QDRANT_COLLECTION}")

    # Create payload indexes for metadata filtering
    _create_payload_indexes(client)


def _create_payload_indexes(client: QdrantClient) -> None:
    """
    Create payload indexes for efficient metadata filtering.

    Indexes:
        - access_roles: keyword (list of permitted roles)
        - department: keyword (engineering, finance, marketing, hr, general)
        - content_type: keyword (technical, financial, expense, etc.)
        - chunk_type: keyword (child, parent, atomic)
        - parent_id: keyword (parent chunk reference)
    """
    indexes = [
        ("access_roles", PayloadSchemaType.KEYWORD),
        ("department", PayloadSchemaType.KEYWORD),
        ("content_type", PayloadSchemaType.KEYWORD),
        ("chunk_type", PayloadSchemaType.KEYWORD),
        ("parent_id", PayloadSchemaType.KEYWORD),
    ]

    for field_name, field_type in indexes:
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field_name,
                field_schema=field_type,
            )
        except Exception:
            # Index may already exist — safe to ignore
            pass


def ensure_collection() -> None:
    """
    Ensure collection exists and is properly configured.
    Safe to call multiple times — idempotent.
    """
    initialize_collection()
