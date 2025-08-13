from __future__ import annotations
from pathlib import Path
from sqlalchemy.orm import Session
from ..models import Base, Broker, SourceFile
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

def bootstrap_broker(session: Session, name: str) -> Broker:
    b = session.query(Broker).filter_by(name=name).first()
    if not b:
        b = Broker(name=name)
        session.add(b)
        session.commit()
    return b
