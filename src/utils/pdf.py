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
