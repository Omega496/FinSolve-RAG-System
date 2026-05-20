"""
BGE-M3 embedding wrapper.
Provides dense, sparse, and hybrid embeddings for FinSolve RAG.
"""

import os
from typing import Optional

from FlagEmbedding import BGEM3FlagModel

# ─── Configuration ─────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
BATCH_SIZE = 32  # Adjust based on available memory

# ─── Singleton Model ──────────────────────────────────────────────────
_model: Optional[BGEM3FlagModel] = None


def _get_model() -> BGEM3FlagModel:
    """
    Get or load the BGE-M3 model (cached after first load).

    Returns:
        Loaded BGEM3FlagModel instance
    """
    global _model

    if _model is None:
        _model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)

    return _model


def encode_dense(texts: list[str]) -> list[list[float]]:
    """
    Generate dense (semantic) embeddings for texts.

    Args:
        texts: List of text strings to embed

    Returns:
        List of dense embedding vectors (1024 dimensions each)
    """
    model = _get_model()

    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        output = model.encode(batch, return_dense=True, return_sparse=False, return_colbert_vecs=False)
        all_embeddings.extend(output["dense"].tolist())

    return all_embeddings


def encode_sparse(texts: list[str]) -> list[dict]:
    """
    Generate sparse (BM25-style) vectors for texts.

    Args:
        texts: List of text strings to encode

    Returns:
        List of sparse vector dicts with 'indices' and 'values' keys
    """
    model = _get_model()

    all_sparse = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        output = model.encode(batch, return_dense=False, return_sparse=True, return_colbert_vecs=False)
        all_sparse.extend(output["lexical_weights"])

    return all_sparse


def encode_both(texts: list[str]) -> list[dict]:
    """
    Generate both dense and sparse vectors for hybrid retrieval.

    Args:
        texts: List of text strings to encode

    Returns:
        List of dicts with 'dense' and 'sparse' keys:
        [
            {
                "dense": [0.012, -0.034, ...],  # 1024-dim
                "sparse": {"indices": [42, 107, ...], "values": [0.5, 0.3, ...]}
            },
            ...
        ]
    """
    model = _get_model()

    all_vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        output = model.encode(
            batch,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )

        for j in range(len(batch)):
            all_vectors.append({
                "dense": output["dense"][j].tolist(),
                "sparse": output["lexical_weights"][j],
            })

    return all_vectors


def clear_cache() -> None:
    """Clear the cached model to free memory."""
    global _model
    _model = None
