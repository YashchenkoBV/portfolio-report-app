"""PDF helper utilities.

This module wraps ``pdfplumber`` to provide simple functions to read text
from PDF files. ``read_text`` reads a limited number of pages (useful for
detecting the correct extractor), while ``read_text_all`` reads the entire
document. Empty pages are skipped gracefully.

Note: PDF parsing can be slow; when a PDF has many pages, we recommend
limiting scanning to the first few pages to find identifying headers.
"""

import pdfplumber
from pathlib import Path


def read_text(path: str, max_pages: int | None = 3) -> str:
    """Return concatenated text from up to ``max_pages`` pages of a PDF."""
    p = Path(path)
    out = []
    with pdfplumber.open(p) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for page in pages:
            text = page.extract_text() or ""
            out.append(text)
    return "\n".join(out)


def read_text_all(path: str) -> str:
    """Return concatenated text from all pages of a PDF."""
    p = Path(path)
    out = []
    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            out.append(text)
    return "\n".join(out)