"""
hybrid_search.py
----------------
Reciprocal Rank Fusion (RRF) over FAISS (vector) and BM25 (keyword) results.

RRF formula: score(chunk) = Σ 1 / (k + rank_i)
k = 60 is the standard constant from Cormack et al. (2009).

RRF is rank-based so it is immune to score scale differences between
FAISS (cosine sim, roughly 0–1) and BM25 (arbitrary positive integers
normalized to 0–1). Both retrievers contribute equally via their rankings.
"""

from __future__ import annotations

from dataclasses import dataclass
from agents.retrieval.chunker import Chunk

RRF_K = 60   # standard constant — do not tune unless you have eval data


@dataclass
class SearchResult:
    chunk:       Chunk
    cosine_sim:  float   # from FAISS (0.0 if chunk only appeared in BM25)
    bm25_score:  float   # normalized (0.0 if chunk only appeared in FAISS)
    rrf_score:   float
    faiss_rank:  int     # 1-based rank in FAISS results (ABSENT_RANK if absent)
    bm25_rank:   int     # 1-based rank in BM25 results (ABSENT_RANK if absent)


def hybrid_search(
    faiss_results: list[tuple[Chunk, float]],
    bm25_results:  list[tuple[Chunk, float]],
    top_k: int = 5,
) -> list[SearchResult]:
    """
    Fuse FAISS and BM25 results via RRF.
    Returns top_k SearchResult objects sorted by rrf_score descending.
    """
    ABSENT_RANK = max(len(faiss_results), len(bm25_results), 1) + 1

    # Build lookup: chunk_id → (Chunk, score, rank)
    faiss_map: dict[int, tuple[Chunk, float, int]] = {}
    for rank, (chunk, score) in enumerate(faiss_results, start=1):
        faiss_map[chunk.chunk_id] = (chunk, score, rank)

    bm25_map: dict[int, tuple[Chunk, float, int]] = {}
    for rank, (chunk, score) in enumerate(bm25_results, start=1):
        bm25_map[chunk.chunk_id] = (chunk, score, rank)

    all_ids = set(faiss_map) | set(bm25_map)

    results: list[SearchResult] = []
    for cid in all_ids:
        if cid in faiss_map:
            chunk, cosine_sim, f_rank = faiss_map[cid]
        else:
            # Chunk appeared in BM25 only — get the Chunk object from there
            chunk, _bm25_s, _br = bm25_map[cid]
            cosine_sim = 0.0
            f_rank = ABSENT_RANK

        if cid in bm25_map:
            _, bm25_score, b_rank = bm25_map[cid]
        else:
            bm25_score = 0.0
            b_rank = ABSENT_RANK

        rrf = 1.0 / (RRF_K + f_rank) + 1.0 / (RRF_K + b_rank)

        results.append(SearchResult(
            chunk=chunk,
            cosine_sim=cosine_sim,
            bm25_score=bm25_score,
            rrf_score=rrf,
            faiss_rank=f_rank,
            bm25_rank=b_rank,
        ))

    results.sort(key=lambda r: r.rrf_score, reverse=True)
    return results[:top_k]
