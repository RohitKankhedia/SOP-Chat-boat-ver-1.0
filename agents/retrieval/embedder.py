"""
embedder.py — v3.2 (scikit-learn TF-IDF + SVD, zero downloads)
-----------
Replaces fastembed/sentence-transformers with pure scikit-learn.

No model files downloaded. No ONNX. No PyTorch. No internet needed.
Works in any sandbox that has numpy + scikit-learn installed.

Technique: TF-IDF vectorizer (bigrams, sublinear TF) → TruncatedSVD
(Latent Semantic Analysis) → L2 normalize → 256-dim dense float32 vectors.

LSA (TF-IDF + SVD) captures semantic relationships between terms and
works well for domain-specific documents like banking SOPs where
terminology is consistent and specific.

The fitted pipeline is saved to data/sop_vectorizer.pkl and must
exist before encode_query() can be called. encode_chunks() creates it.
"""

from __future__ import annotations

import functools
import os
import pickle
import sys

import numpy as np

# Ensure torch is never imported (DLL incompatible with Python 3.14 on Windows)
for _mod in list(sys.modules.keys()):
    if _mod == "torch" or _mod.startswith("torch."):
        del sys.modules[_mod]

DIM = 256   # target embedding dimension (LSA components)
VECTORIZER_PATH = os.path.join("data", "sop_vectorizer.pkl")

_pipeline = None  # (TfidfVectorizer, TruncatedSVD) — loaded once per process


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row so inner product equals cosine similarity."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)  # avoid divide-by-zero
    return (matrix / norms).astype(np.float32)


def _save_pipeline(tfidf, svd) -> None:
    os.makedirs(os.path.dirname(VECTORIZER_PATH) or ".", exist_ok=True)
    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump((tfidf, svd), f)


def _load_pipeline():
    global _pipeline
    if _pipeline is None:
        if not os.path.exists(VECTORIZER_PATH):
            raise FileNotFoundError(
                f"Vectorizer not found at {VECTORIZER_PATH}. "
                "Run build_index() first."
            )
        with open(VECTORIZER_PATH, "rb") as f:
            _pipeline = pickle.load(f)
    return _pipeline


# ── Public API (matches original sentence-transformers interface) ─────────────

def encode_chunks(texts: list[str]) -> np.ndarray:
    """
    Fit TF-IDF + SVD on the full chunk corpus and return embeddings.
    Saves the fitted pipeline to disk for later use by encode_query().

    Called ONCE during index build.
    Returns shape (N, DIM), float32, L2-normalized.
    """
    global _pipeline

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD

    print(f"[embedder] Fitting TF-IDF + SVD on {len(texts)} chunks ...")

    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),   # unigrams + bigrams (captures "rate change", "Reg Z")
        sublinear_tf=True,    # apply log(1 + tf) for better scaling
        min_df=1,
        max_features=30_000,
        strip_accents="unicode",
        analyzer="word",
        token_pattern=r"(?u)\b\w+\b",
    )
    X_sparse = tfidf.fit_transform(texts)

    # SVD dimension must be < min(n_docs, n_features)
    n_components = min(DIM, X_sparse.shape[0] - 1, X_sparse.shape[1] - 1)
    n_components = max(n_components, 1)  # at least 1

    svd = TruncatedSVD(n_components=n_components, random_state=42, n_iter=5)
    X_dense = svd.fit_transform(X_sparse)

    _pipeline = (tfidf, svd)
    _save_pipeline(tfidf, svd)

    embeddings = _normalize(X_dense)
    print(f"[embedder] Done — {embeddings.shape[1]}-dim vectors, "
          f"variance explained: {svd.explained_variance_ratio_.sum():.1%}")
    return embeddings


def encode_query(query: str) -> np.ndarray:
    """
    Transform a query string using the fitted TF-IDF + SVD pipeline.
    Returns shape (DIM,), float32, L2-normalized.
    """
    tfidf, svd = _load_pipeline()
    X_sparse = tfidf.transform([query])
    X_dense  = svd.transform(X_sparse)
    return _normalize(X_dense)[0]
