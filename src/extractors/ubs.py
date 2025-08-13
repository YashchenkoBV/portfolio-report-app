from __future__ import annotations
import re
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import SourceFile, Valuation
from ..utils.pdf import read_text_all
from ..services.bootstrap import (
    bootstrap_broker, get_or_create_account,
    parse_money_to_float, parse_date_en
)
from .base import BaseExtractor

ASOF_RX = re.compile(r"\bas of\s+([A-Za-z]{3,9}\s+\d{1,2}\s+\d{4})", re.IGNORECASE)

class UBSExtractor(BaseExtractor):
    name = "UBS"

    def detect(self, lower_text: str) -> bool:
        keys = [
            "portfolio holdings",
            "equity summary",
            "asset allocation by account",
            "executive summary",
            "ubs financial services",
            "ubs fs"
        ]
        return any(k in lower_text for k in keys)

    def _extract_asof(self, text: str):
        m = ASOF_RX.search(text)
        return parse_date_en(m.group(1)) if m else None

    def _extract_total(self, text: str):
        total = None
        for line in text.splitlines():
            if "total portfolio" in line.lower():
                v = parse_money_to_float(line)
                if v is not None:
                    total = v
        return total

    def summary(self, path: str) -> dict:
        t = read_text_all(path)
        return {
            "broker": self.name,
            "asof": str(self._extract_asof(t)) if self._extract_asof(t) else None,
            "total_portfolio": self._extract_total(t),
        }

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "UBS Consolidated", "USD")
        sm = self.summary(path)
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=None if sm["asof"] is None else datetime.strptime(sm["asof"], "%Y-%m-%d").date())
        session.add(sf); session.commit()
        if sm["total_portfolio"] is not None:
            asof = datetime.strptime(sm["asof"], "%Y-%m-%d").date() if sm["asof"] else datetime.today().date()
            session.add(Valuation(date=asof, account_id=acc.id, total_value=sm["total_portfolio"], method="reported"))
            session.commit()
        return sm
