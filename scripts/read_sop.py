"""
read_sop.py
-----------
Reads a SOP Word document (.docx) and extracts all text —
paragraphs AND tables — into a clean plain-text file.

Usage:
    python scripts/read_sop.py

Output:
    data/SOP_extracted.txt   (used by the chatbot later)
"""

import os
from docx import Document


# ── Config ────────────────────────────────────────────────────────────
SOP_FILE = os.path.join("data", "SOP_Bank_Rate_Change_Process.docx")
OUTPUT_FILE = os.path.join("data", "SOP_extracted.txt")


def extract_text_from_docx(filepath):
    """
    Opens the .docx file and pulls out:
      - All paragraph text (headings, bullets, numbered steps, plain text)
      - All table cell text (row by row, cell by cell)
    Returns a single string with everything joined by newlines.
    """
    doc = Document(filepath)
    lines = []

    # We iterate over the document body in order so headings, paragraphs,
    # and tables appear in the same sequence as in the original document.
    for block in doc.element.body:

        # ── Paragraph (includes headings, bullets, numbered lists) ──
        tag = block.tag.split("}")[-1]  # strip XML namespace

        if tag == "p":
            # Find the matching Paragraph object
            from docx.oxml.ns import qn
            text = "".join(
                node.text or ""
                for node in block.iter()
                if node.tag == qn("w:t")
            )
            if text.strip():
                lines.append(text.strip())

        # ── Table ──────────────────────────────────────────────────
        elif tag == "tbl":
            from docx.table import Table
            tbl = Table(block, doc)
            for row in tbl.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    # Join cells with  |  so it reads like:  Role | Contact | Action
                    lines.append(" | ".join(row_cells))
            lines.append("")  # blank line after each table

    return "\n".join(lines)


def main():
    # ── Check file exists ─────────────────────────────────────────
    if not os.path.exists(SOP_FILE):
        print(f"ERROR: Could not find '{SOP_FILE}'")
        print("Make sure you have copied the SOP into the data/ folder.")
        return

    print(f"Reading: {SOP_FILE}")
    text = extract_text_from_docx(SOP_FILE)

    # ── Save extracted text ───────────────────────────────────────
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    # ── Summary ───────────────────────────────────────────────────
    lines = [l for l in text.splitlines() if l.strip()]
    words = len(text.split())

    print(f"\n✅ Extraction complete!")
    print(f"   Lines extracted : {len(lines)}")
    print(f"   Word count      : {words}")
    print(f"   Saved to        : {OUTPUT_FILE}")
    print("\n--- Preview (first 20 lines) ---")
    for line in lines[:20]:
        print(" ", line)


if __name__ == "__main__":
    main()
