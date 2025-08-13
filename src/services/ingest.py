from __future__ import annotations
import os
from sqlalchemy.orm import Session
from ..utils.pdf import read_text_all
from ..models import SourceFile
from ..extractors.ubs import UBSExtractor
from ..extractors.raymond_james import RaymondJamesExtractor
from ..extractors.freedom_finance import FreedomFinanceExtractor

EXTRACTORS = [UBSExtractor(), RaymondJamesExtractor(), FreedomFinanceExtractor()]

def detect_extractor(path: str):
    text = read_text_all(path).lower()  # scan full file; headers vary
    for ex in EXTRACTORS:
        if ex.detect(text):
            return ex
    return None

def already_ingested(session: Session, path: str) -> bool:
    return session.query(SourceFile).filter(SourceFile.path == path).first() is not None

def ingest_file(session: Session, path: str):
    ex = detect_extractor(path)
    if not ex:
        raise ValueError(f"No extractor matched: {path}")
    # do not re-ingest same path twice
    if already_ingested(session, path):
        return {"file": os.path.basename(path), "status": "skipped", "reason": "already ingested", "broker": ex.name}
    return ex.parse(session, path)

def ingest_all(session: Session, data_dir: str = "data"):
    results = []
    if not os.path.isdir(data_dir):
        return [{"file": None, "status": "error", "error": f"missing folder {data_dir}"}]
    for fn in sorted(os.listdir(data_dir)):
        if not fn.lower().endswith(".pdf"):
            continue
        p = os.path.join(data_dir, fn)
        ex = detect_extractor(p)
        if not ex:
            results.append({"file": fn, "status": "skipped", "reason": "no match"}); continue
        try:
            if already_ingested(session, p):
                results.append({"file": fn, "status": "skipped", "reason": "already ingested", "broker": ex.name})
            else:
                res = ex.parse(session, p)
                results.append({"file": fn, "status": "ok", "broker": ex.name, "summary": res})
        except Exception as e:
            results.append({"file": fn, "status": "error", "error": str(e)})
    return results
