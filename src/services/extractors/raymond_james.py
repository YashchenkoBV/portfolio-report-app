# src/services/extractors/raymond_james.py
from __future__ import annotations
import re
from datetime import datetime
from sqlalchemy.orm import Session
from ...models import SourceFile, Valuation
from ...utils.pdf import read_text
from ...services.bootstrap import bootstrap_broker, get_or_create_account, parse_money_to_float
from .base import BaseExtractor

ASOF_RX = re.compile(r"\bAs\s*of\s*(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
CURVAL_RX = re.compile(r"\bCurrent\s*Value\b.*?([-$]?\$?\s?\d[\d,\s]*\.?\d*)", re.IGNORECASE | re.DOTALL)

class RaymondJamesExtractor(BaseExtractor):
    name = "Raymond James"

    def detect(self, lower_text: str) -> bool:
        return ("raymond james | client access | my accounts | portfolio" in lower_text) or ("current value" in lower_text)

    def _extract_asof(self, text: str):
        m = ASOF_RX.search(text)
        if not m:
            return None
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y").date()
        except ValueError:
            return None

    def _extract_total(self, text: str):
        # line-by-line first
        for line in text.splitlines():
            if "current value" in line.lower():
                v = parse_money_to_float(line)
                if v is not None:
                    return v
        # wrapped layout
        m = CURVAL_RX.search(text)
        return parse_money_to_float(m.group(0)) if m else None

    def summary(self, path: str) -> dict:
        t = read_text(path, max_pages=4)
        asof = self._extract_asof(t)
        return {"broker": self.name, "asof": str(asof) if asof else None, "current_value": self._extract_total(t)}

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "RJ Consolidated", "USD")
        sm = self.summary(path)
        session.add(SourceFile(broker_id=broker.id, path=path, asof_date=None if sm["asof"] is None else datetime.strptime(sm["asof"], "%Y-%m-%d").date()))
        session.commit()
        if sm["current_value"] is not None:
            asof = datetime.strptime(sm["asof"], "%Y-%m-%d").date() if sm["asof"] else datetime.today().date()
            session.add(Valuation(date=asof, account_id=acc.id, total_value=sm["current_value"], method="reported")); session.commit()
        return sm
