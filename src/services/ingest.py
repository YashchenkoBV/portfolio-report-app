"""Ingestion services for the portfolio report app.

This module coordinates reading PDF files and delegating to the
appropriate extractor. It exposes functions to ingest a single file and
to ingest all PDFs in a directory. It also provides a helper to
detect which extractor should handle a given file by inspecting its
contents.
"""

from __future__ import annotations

import os
from sqlalchemy.orm import Session
from ..utils.pdf import read_text
from .extractors.ubs import UBSExtractor
from .extractors.raymond_james import RaymondJamesExtractor
from .extractors.freedom_finance import FreedomFinanceExtractor
from ..models import SourceFile


# List of extractor instances to try. Order matters: more specific
# extractors should appear earlier.
EXTRACTORS = [
    UBSExtractor(),
    RaymondJamesExtractor(),
    FreedomFinanceExtractor(),
]


def detect_extractor(path: str):
    """Return an extractor instance that recognises the given PDF.

    We read up to the first three pages of the PDF as lower‑case text and
    test each extractor's ``detect`` method. The first match wins. If
    no extractor matches, return ``None``.
    """
    try:
        text = read_text(path, max_pages=3).lower()
    except Exception:
        return None
    for ex in EXTRACTORS:
        if ex.detect(text):
            return ex
    return None


def already_ingested(session: Session, path: str) -> bool:
    """Return True if a SourceFile with the given path exists in the database."""
    return session.query(SourceFile).filter(SourceFile.path == path).first() is not None


def ingest_file(session: Session, path: str):
    """Ingest a single PDF file into the database.

    The file is first matched against available extractors. If a match is
    found, the extractor's ``parse`` method is invoked. If the file has
    already been ingested (as recorded in the ``SourceFile`` table), a
    dictionary describing the skip reason is returned.
    """
    ex = detect_extractor(path)
    if not ex:
        raise ValueError(f"No extractor matched: {path}")
    if already_ingested(session, path):
        return {
            "file": os.path.basename(path),
            "status": "skipped",
            "reason": "already ingested",
            "broker": ex.name,
        }
    return ex.parse(session, path)


def ingest_all(session: Session, data_dir: str = "data"):
    """Ingest all PDF files in the given directory.

    Files are processed in sorted order. The result is a list of
    dictionaries summarising each file's ingestion status. Files that do
    not match any extractor are skipped with a reason. Files that have
    already been ingested are also skipped.
    """
    results = []
    if not os.path.isdir(data_dir):
        return [
            {
                "file": None,
                "status": "error",
                "error": f"missing folder {data_dir}",
            }
        ]
    for fn in sorted(os.listdir(data_dir)):
        if not fn.lower().endswith(".pdf"):
            continue
        path = os.path.join(data_dir, fn)
        ex = detect_extractor(path)
        if not ex:
            results.append(
                {
                    "file": fn,
                    "status": "skipped",
                    "reason": "no match",
                }
            )
            continue
        try:
            if already_ingested(session, path):
                results.append(
                    {
                        "file": fn,
                        "status": "skipped",
                        "reason": "already ingested",
                        "broker": ex.name,
                    }
                )
            else:
                sm = ex.parse(session, path)
                results.append(
                    {
                        "file": fn,
                        "status": "ok",
                        "broker": ex.name,
                        "summary": sm,
                    }
                )
        except Exception as e:
            results.append(
                {
                    "file": fn,
                    "status": "error",
                    "error": str(e),
                }
            )
    return results