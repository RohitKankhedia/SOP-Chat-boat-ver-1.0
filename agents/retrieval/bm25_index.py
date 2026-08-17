"""
bm25_index.py
-------------
BM25Okapi keyword search over SOP chunks.

BM25 complements vector similarity by excelling at exact term matches
(e.g. regulation names: "Reg Z", "MLA", "ECOA", step numbers).
Scores are normalized to [0, 1] for comparability with cosine similarity.

Persists to: data/sop_bm25.pkl
"""

from __future__ import annotations

import os
import pickle
import re

from agents.retrieval.chunker import Chunk

BM25_PATH = os.path.join("data", "sop_bm25.pkl")


def _tokenize(text: str) -> list[str]:
    """
    Simple tokenizer: lowercase alphanumeric tokens.
    No stopword removal — banking terms like "who", "what", "reg" are meaningful.
    """
    return re.findall(r"[a-z0-9]+", text.lower())


def build(chunks: list[Chunk]):
    """Build a BM25Okapi index over chunk texts. Returns the BM25 object."""
    from rank_bm25 import BM25Okapi
    tokenized = [_tokenize(c.text) for c in chunks]
    return BM25Okapi(tokenized)


def search(
    bm25,
    chunks: list[Chunk],
    query: str,
    top_k: int = 20,
) -> list[tuple[Chunk, float]]:
    """
    Search the BM25 index.
    Returns [(chunk, normalized_score), ...] sorted descending.
    Scores are normalized to [0, 1] by dividing by the max score in the result.
    Chunks with score 0 are excluded.
    """
    tokens = _tokenize(query)
    scores = bm25.get_scores(tokens)

    max_score = float(scores.max()) if scores.max() > 0 else 1.0
    normalized = scores / max_score

    top_indices = scores.argsort()[::-1][:top_k]
    results = []
    for idx in top_indices:
        if normalized[idx] > 0:
            results.append((chunks[int(idx)], float(normalized[idx])))
    return results


def save(bm25) -> None:
    os.makedirs(os.path.dirname(BM25_PATH) or ".", exist_ok=True)
    with open(BM25_PATH, "wb") as f:
        pickle.dump(bm25, f)


def load():
    """Returns a BM25Okapi object or None if not found."""
    if not os.path.exists(BM25_PATH):
        return None
    try:
        with open(BM25_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"[bm25_index] Failed to load: {e}")
        return None
