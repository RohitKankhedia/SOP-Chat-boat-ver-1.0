"""
chunker.py
----------
Converts SOP documents (.docx, .pdf) into Chunk objects with
section-level metadata for retrieval.

Each Chunk carries:
  - source_file      : filename (e.g. "SOP_Bank_Rate_Change_Process.docx")
  - section_heading  : nearest heading above the chunk text
  - text             : the chunk content (max ~280 tokens)
  - token_count      : approximate token count
  - char_start       : character offset in source document (for debugging)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

MAX_TOKENS = 280        # approximate token budget per chunk (word_count × 1.3)
OVERLAP_WORDS = 30      # words carried over from previous chunk into next


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_id:        int
    source_file:     str
    section_heading: str
    text:            str
    token_count:     int
    char_start:      int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Chunk":
        return Chunk(**d)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _get_para_text(block) -> str:
    """Extract plain text from a raw docx paragraph element."""
    return "".join(
        node.text or ""
        for node in block.iter()
        if node.tag == qn("w:t")
    )


def _get_style_val(block) -> str:
    """Return the paragraph style value (e.g. 'Heading1') from a raw element."""
    pPr = block.find(qn("w:pPr"))
    if pPr is None:
        return ""
    pStyle = pPr.find(qn("w:pStyle"))
    if pStyle is None:
        return ""
    return pStyle.get(qn("w:val"), "")


def _is_heading(block) -> bool:
    """Detect headings by style name or numbered-heading text pattern."""
    style_val = _get_style_val(block).lower()
    if "heading" in style_val or "title" in style_val:
        return True
    text = _get_para_text(block).strip()
    # Match "1.", "2.1", "3.2.4 " style numbered headings (short lines only)
    return bool(re.match(r"^\d+(\.\d+)*[\.\s]\s*\S", text) and len(text) < 100)


def _overlap_tail(text: str, n_words: int = OVERLAP_WORDS) -> str:
    """Return the last n_words of text as the overlap seed for the next chunk."""
    words = text.split()
    if len(words) <= n_words:
        return ""
    return " ".join(words[-n_words:])


# ── Docx chunker ──────────────────────────────────────────────────────────────

def chunk_docx(filepath: str, starting_chunk_id: int = 0) -> list[Chunk]:
    source_file = os.path.basename(filepath)
    doc = Document(filepath)
    chunks: list[Chunk] = []
    chunk_id = starting_chunk_id

    current_section = "Introduction"
    buffer: list[str] = []
    buffer_tokens = 0
    overlap = ""          # carried from previous chunk
    char_cursor = 0

    def flush(section: str, char_start: int) -> Chunk | None:
        nonlocal buffer, buffer_tokens, chunk_id
        raw = " ".join(buffer).strip()
        if not raw:
            return None
        text = (overlap + " " + raw).strip() if overlap else raw
        c = Chunk(
            chunk_id=chunk_id,
            source_file=source_file,
            section_heading=section,
            text=text,
            token_count=_approx_tokens(text),
            char_start=char_start,
        )
        chunk_id += 1
        buffer = []
        buffer_tokens = 0
        return c

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]

        if tag == "p":
            para_text = _get_para_text(block).strip()
            if not para_text:
                continue

            if _is_heading(block):
                # Flush pending buffer before starting new section
                c = flush(current_section, char_cursor)
                if c:
                    chunks.append(c)
                    overlap = _overlap_tail(c.text)
                current_section = para_text
                char_cursor += len(para_text) + 1
                continue

            tok = _approx_tokens(para_text)
            # Flush if adding this paragraph would exceed the token budget
            if buffer_tokens + tok > MAX_TOKENS and buffer:
                c = flush(current_section, char_cursor)
                if c:
                    chunks.append(c)
                    overlap = _overlap_tail(c.text)

            buffer.append(para_text)
            buffer_tokens += tok
            char_cursor += len(para_text) + 1

        elif tag == "tbl":
            # Always flush before a table — tables are self-contained
            c = flush(current_section, char_cursor)
            if c:
                chunks.append(c)
                overlap = ""          # no overlap into/from tables

            tbl = Table(block, doc)
            rows = []
            for row in tbl.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    rows.append(" | ".join(cells))
            table_text = "\n".join(rows).strip()
            if table_text:
                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    source_file=source_file,
                    section_heading=current_section,
                    text=table_text,
                    token_count=_approx_tokens(table_text),
                    char_start=char_cursor,
                ))
                chunk_id += 1
            char_cursor += len(table_text) + 1

    # Final flush
    c = flush(current_section, char_cursor)
    if c:
        chunks.append(c)

    return chunks


# ── PDF chunker ───────────────────────────────────────────────────────────────

def chunk_pdf(filepath: str, starting_chunk_id: int = 0) -> list[Chunk]:
    source_file = os.path.basename(filepath)
    chunks: list[Chunk] = []
    chunk_id = starting_chunk_id

    if not PDFPLUMBER_AVAILABLE:
        print(f"[chunker] pdfplumber not installed — skipping {source_file}")
        return []

    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            # Scanned page: less than 50 chars of native text → try OCR
            if len(text.strip()) < 50 and OCR_AVAILABLE:
                try:
                    images = convert_from_path(
                        filepath, first_page=page_num, last_page=page_num, dpi=200
                    )
                    text = pytesseract.image_to_string(images[0])
                except Exception as e:
                    print(f"[chunker] OCR failed on page {page_num}: {e}")

            if not text.strip():
                continue

            # Best-effort heading detection: first short non-sentence line on the page
            section = f"Page {page_num}"
            for line in text.split("\n")[:6]:
                line = line.strip()
                if line and len(line) < 80 and not line.endswith(".") and len(line.split()) > 1:
                    section = line
                    break

            # Split page text into token-bounded chunks with word-level overlap
            words = text.split()
            word_buf: list[str] = []
            for word in words:
                word_buf.append(word)
                if _approx_tokens(" ".join(word_buf)) >= MAX_TOKENS:
                    chunk_text = " ".join(word_buf)
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        source_file=source_file,
                        section_heading=section,
                        text=chunk_text,
                        token_count=_approx_tokens(chunk_text),
                    ))
                    chunk_id += 1
                    word_buf = word_buf[-OVERLAP_WORDS:]   # keep overlap

            if word_buf:
                chunk_text = " ".join(word_buf).strip()
                if chunk_text:
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        source_file=source_file,
                        section_heading=section,
                        text=chunk_text,
                        token_count=_approx_tokens(chunk_text),
                    ))
                    chunk_id += 1

    return chunks


# ── Dispatcher ────────────────────────────────────────────────────────────────

def chunk_file(filepath: str, starting_chunk_id: int = 0) -> list[Chunk]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".docx":
        return chunk_docx(filepath, starting_chunk_id)
    elif ext == ".pdf":
        return chunk_pdf(filepath, starting_chunk_id)
    else:
        print(f"[chunker] Unsupported file type: {filepath}")
        return []
