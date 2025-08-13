from __future__ import annotations
import os
from sqlalchemy.orm import Session
from ..utils.pdf import read_text
from ..extractors.ubs import UBSExtractor
from ..extractors.raymond_james import RaymondJamesExtractor
from ..extractors.freedom_finance import FreedomFinanceExtractor

EXTRACTORS = [UBSExtractor(), RaymondJamesExtractor(), FreedomFinanceExtractor()]

def detect_extractor(path: str):
    text = read_text(path, max_pages=2).lower()
    for ex in EXTRACTORS:
        if ex.detect(text):
            return ex
    return None

def ingest_file(session: Session, path: str):
    ex = detect_extractor(path)
    if not ex:
        raise ValueError(f"No extractor matched: {path}")
    return ex.parse(session, path)

def ingest_all(session: Session, data_dir: str = "data"):
    results = []
    for fn in os.listdir(data_dir):
        if not fn.lower().endswith(".pdf"):
            continue
        p = os.path.join(data_dir, fn)
        ex = detect_extractor(p)
        if not ex:
            results.append({"file": fn, "status": "skipped", "reason": "no match"}); continue
        try:
            res = ex.parse(session, p)
            results.append({"file": fn, "status": "ok", "broker": ex.name, "summary": res})
        except Exception as e:
            results.append({"file": fn, "status": "error", "error": str(e)})
    return results
