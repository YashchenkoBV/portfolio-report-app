from __future__ import annotations
import re
from datetime import date, datetime
from sqlalchemy.orm import Session
from ..models import SourceFile, Valuation
from ..utils.pdf import read_text_all
from ..services.bootstrap import bootstrap_broker, get_or_create_account, parse_money_to_float, parse_date_en
from .base import BaseExtractor

ASOF_RX = re.compile(r"\bas of\s+([A-Za-z]{3,9}\s+\d{1,2}\s+\d{4})", re.IGNORECASE)

class UBSExtractor(BaseExtractor):
    name = "UBS"

    def detect(self, lower_text: str) -> bool:
        # match any of the UBS report variants present in your data
        keys = [
            "portfolio holdings",          # Portfolio Holdings header
            "equity summary",              # Equity Summary header
            "asset allocation by account", # Allocation report
            "ubs fs", "ubs financial services"
        ]
        return any(k in lower_text for k in keys)

    def _extract_asof(self, text: str) -> date | None:
        m = ASOF_RX.search(text)
        if m:
            return parse_date_en(m.group(1))
        return None

    def _extract_total_portfolio(self, text: str) -> float | None:
        total = None
        for line in text.splitlines():
            if "total portfolio" in line.lower():
                val = parse_money_to_float(line)
                if val:
                    total = val
        return total

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "UBS Consolidated", "USD")

        text = read_text_all(path)
        asof = self._extract_asof(text)  # e.g., "as of May 27, 2025" :contentReference[oaicite:2]{index=2}
        total = self._extract_total_portfolio(text)  # e.g., "Total Portfolio $13,072,114.79" :contentReference[oaicite:3]{index=3}

        sf = SourceFile(broker_id=broker.id, path=path, asof_date=asof)
        session.add(sf); session.commit()

        if total:
            session.add(Valuation(date=asof or datetime.today().date(), account_id=acc.id, total_value=total, method="reported"))
            session.commit()

        return {"broker": self.name, "asof": str(asof) if asof else None, "total": total}
