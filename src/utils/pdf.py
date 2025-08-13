import pdfplumber
from pathlib import Path

def read_text(path: str, max_pages: int | None = 3) -> str:
    p = Path(path)
    out = []
    with pdfplumber.open(p) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for page in pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)

def read_text_all(path: str) -> str:
    p = Path(path)
    out = []
    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)

def find_context(lines: list[str], idx: int, window: int = 2) -> str:
    lo = max(0, idx - window)
    hi = min(len(lines), idx + window + 1)
    return "\n".join(lines[lo:hi])
