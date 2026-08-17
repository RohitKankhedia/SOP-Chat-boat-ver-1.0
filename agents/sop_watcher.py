"""
sop_watcher.py
--------------
Watches all SOP files in data/ for changes (not just one hardcoded file).

New functions:
  get_all_file_mtimes()   — returns {filepath: mtime} for all supported files
  check_and_reload_all()  — detects any addition, removal, or modification

Legacy stubs (kept for Tab 1 compatibility):
  load_sop_text()         — extracts text from the main rate change SOP for Tab 1
  check_and_reload()      — single-file check (used by legacy code paths)
"""

from __future__ import annotations

import glob
import os

DATA_DIR             = "data"
SUPPORTED_EXTENSIONS = {".docx", ".pdf"}


# ── Multi-file watching (new) ─────────────────────────────────────────────────

def get_all_sop_files(data_dir: str = DATA_DIR) -> list[str]:
    """Return sorted list of all supported SOP files in data_dir."""
    files: list[str] = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(glob.glob(os.path.join(data_dir, f"*{ext}")))
    return sorted(files)


def get_all_file_mtimes(data_dir: str = DATA_DIR) -> dict[str, float]:
    """Return {filepath: mtime} for every supported SOP file in data_dir."""
    return {f: os.path.getmtime(f) for f in get_all_sop_files(data_dir)}


def check_and_reload_all(
    last_mtimes: dict[str, float],
    data_dir: str = DATA_DIR,
) -> tuple[dict[str, float], bool]:
    """
    Compare current file mtimes against the stored snapshot.
    Returns (current_mtimes, changed: bool).

    changed=True if any file was added, removed, or modified.
    When changed=True, caller should trigger sop_retriever.rebuild().
    """
    current_mtimes = get_all_file_mtimes(data_dir)
    changed = current_mtimes != last_mtimes
    return current_mtimes, changed


# ── Legacy stubs for Tab 1 / backward compatibility ──────────────────────────

_MAIN_SOP = os.path.join(DATA_DIR, "SOP_Bank_Rate_Change_Process.docx")


def get_last_modified(filepath: str) -> float:
    return os.path.getmtime(filepath) if os.path.exists(filepath) else 0.0


def load_sop_text() -> tuple[str, float]:
    """
    Extract text from the main rate change SOP file.
    Used by Tab 1's retention offer agent (not by the RAG retriever).
    Returns (text, last_modified_timestamp).
    """
    if not os.path.exists(_MAIN_SOP):
        return "", 0.0
    try:
        from docx import Document
        from docx.oxml.ns import qn
        doc   = Document(_MAIN_SOP)
        lines = []
        for block in doc.element.body:
            tag = block.tag.split("}")[-1]
            if tag == "p":
                text = "".join(
                    node.text or ""
                    for node in block.iter()
                    if node.tag == qn("w:t")
                )
                if text.strip():
                    lines.append(text.strip())
        return "\n".join(lines), os.path.getmtime(_MAIN_SOP)
    except Exception:
        return "", get_last_modified(_MAIN_SOP)


def check_and_reload(last_modified_time: float) -> tuple[float, str | None]:
    """
    Legacy single-file change check for the main rate change SOP.
    Returns (current_mtime, new_text_or_None).
    """
    current = get_last_modified(_MAIN_SOP)
    if current > last_modified_time:
        text, _ = load_sop_text()
        return current, text
    return last_modified_time, None
