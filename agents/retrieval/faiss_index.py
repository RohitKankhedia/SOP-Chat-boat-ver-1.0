"""
faiss_index.py — v3.2 (pure numpy, no FAISS required)
--------------
Replaces faiss-cpu with numpy matrix multiplication for cosine similarity.

For our scale (~200–500 chunks across 5 SOPs), numpy dot-product search
is instant (<1ms per query) and requires zero additional packages.

Persists to:
  data/sop_vectors.npy — embedding matrix (N x DIM)
  data/sop_chunks.json — chunk metadata (parallel array)

The variable named INDEX_PATH kept the same name so indexer.py's stale
check continues to work without changes.
"""

from __future__ import annotations

import json
import os

import numpy as np

from agents.retrieval.chunker import Chunk

INDEX_PATH  = os.path.join("data", "sop_vectors.npy")
CHUNKS_PATH = os.path.join("data", "sop_chunks.json")


def build(chunks: list[Chunk], embeddings: np.ndarray) -> np.ndarray:
    """
    'Build' the index — for numpy this is just returning the matrix.
    embeddings: shape (N, DIM), float32, L2-normalized
    Returns the same matrix (acts as the index).
    """
    return embeddings.astype(np.float32)


def search(
    index: np.ndarray,
    chunks: list[Chunk],
    query_vec: np.ndarray,
    top_k: int = 20,
) -> list[tuple[Chunk, float]]:
    """
    Cosine similarity search via dot product on L2-normalized vectors.
    index: shape (N, DIM), float32
    query_vec: shape (DIM,), float32, L2-normalized
    Returns [(chunk, cosine_similarity), ...] sorted descending.
    """
    scores = index @ query_vec.astype(np.float32)          # (N,)
    k = min(top_k, len(chunks))
    top_indices = np.argsort(scores)[::-1][:k]             # descending
    return [(chunks[int(i)], float(scores[i])) for i in top_indices]


def save(index: np.ndarray, chunks: list[Chunk]) -> None:
    os.makedirs(os.path.dirname(INDEX_PATH) or ".", exist_ok=True)
    np.save(INDEX_PATH, index)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=2)


def load() -> tuple:
    """
    Load persisted vectors and chunks.
    Returns (np.ndarray, list[Chunk]) or (None, None) if not found.
    """
    if not os.path.exists(INDEX_PATH) or not os.path.exists(CHUNKS_PATH):
        return None, None
    try:
        index = np.load(INDEX_PATH)
        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            chunk_dicts = json.load(f)
        chunks = [Chunk.from_dict(d) for d in chunk_dicts]
        return index, chunks
    except Exception as e:
        print(f"[faiss_index] Failed to load: {e}")
        return None, None
