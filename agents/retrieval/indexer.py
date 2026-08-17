"""
indexer.py
----------
Orchestrates the full document ingestion pipeline:
  scan data/ → chunk all supported files → embed → build FAISS + BM25 → save

Supports incremental cache: only rebuilds if any SOP file is newer
than the persisted index files.
"""

from __future__ import annotations

import glob
import os
import time

from agents.retrieval import chunker, embedder, faiss_index, bm25_index
from agents.retrieval.embedder import VECTORIZER_PATH
from agents.retrieval.chunker import Chunk

DATA_DIR  = "data"
SUPPORTED = {".docx", ".pdf"}


def get_sop_files(data_dir: str = DATA_DIR) -> list[str]:
    """Return sorted list of all supported SOP file paths in data_dir."""
    files: list[str] = []
    for ext in SUPPORTED:
        files.extend(glob.glob(os.path.join(data_dir, f"*{ext}")))
    return sorted(files)


def get_file_mtimes(data_dir: str = DATA_DIR) -> dict[str, float]:
    """Return {filepath: mtime} for all supported SOP files."""
    return {f: os.path.getmtime(f) for f in get_sop_files(data_dir)}


def _index_is_stale(data_dir: str = DATA_DIR) -> bool:
    """
    Return True if any SOP source file is newer than the oldest index file,
    or if any index file is missing.
    """
    index_files = [
        faiss_index.INDEX_PATH,
        faiss_index.CHUNKS_PATH,
        bm25_index.BM25_PATH,
        VECTORIZER_PATH,
    ]
    if not all(os.path.exists(p) for p in index_files):
        return True

    oldest_index = min(os.path.getmtime(p) for p in index_files)
    sop_files = get_sop_files(data_dir)
    if not sop_files:
        return False
    newest_sop = max(os.path.getmtime(f) for f in sop_files)
    return newest_sop > oldest_index


def build_index(data_dir: str = DATA_DIR) -> tuple:
    """
    Chunk all SOP files, embed, build FAISS + BM25, and persist to disk.
    Returns (faiss_index, bm25_index, all_chunks).
    Returns (None, None, []) if no SOP files found or all fail.
    """
    files = get_sop_files(data_dir)
    if not files:
        print("[indexer] No SOP files found in data/")
        return None, None, []

    print(f"[indexer] Indexing {len(files)} file(s)...")
    t0 = time.time()

    all_chunks: list[Chunk] = []
    next_id = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            file_chunks = chunker.chunk_file(fpath, starting_chunk_id=next_id)
            all_chunks.extend(file_chunks)
            next_id += len(file_chunks)
            print(f"  ✓ {fname}: {len(file_chunks)} chunks")
        except Exception as e:
            print(f"  ✗ {fname}: failed — {e}")

    if not all_chunks:
        print("[indexer] No chunks produced — check SOP files.")
        return None, None, []

    # Embed all chunks
    print(f"[indexer] Embedding {len(all_chunks)} chunks ...")
    texts = [c.text for c in all_chunks]
    embeddings = embedder.encode_chunks(texts)

    # Build and save FAISS index
    print("[indexer] Building FAISS index ...")
    fi = faiss_index.build(all_chunks, embeddings)
    faiss_index.save(fi, all_chunks)

    # Build and save BM25 index
    print("[indexer] Building BM25 index ...")
    bi = bm25_index.build(all_chunks)
    bm25_index.save(bi)

    elapsed = time.time() - t0
    print(f"[indexer] Done in {elapsed:.1f}s — {len(all_chunks)} chunks across {len(files)} files.")
    return fi, bi, all_chunks


def load_or_build(data_dir: str = DATA_DIR) -> tuple:
    """
    Load cached indexes if they are up-to-date, otherwise rebuild.
    Returns (faiss_index, bm25_index, all_chunks).
    """
    if not _index_is_stale(data_dir):
        print("[indexer] Loading cached indexes ...")
        try:
            fi, chunks = faiss_index.load()
            bi = bm25_index.load()
            if fi is not None and bi is not None and chunks:
                print(f"[indexer] Loaded {len(chunks)} chunks from cache.")
                return fi, bi, chunks
            else:
                print("[indexer] Cache incomplete — rebuilding ...")
        except Exception as e:
            print(f"[indexer] Cache load failed ({e}) — rebuilding ...")

    return build_index(data_dir)
