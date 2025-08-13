from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import Broker, Account, SourceFile, Valuation
from ..services.ingest import bootstrap_broker
from .base import BaseExtractor
from ..utils.pdf import read_text

class UBSExtractor(BaseExtractor):
    name = "UBS"

    def detect(self, lower_text: str) -> bool:
        keys = ["ubs financial services", "equity summary", "asset allocation by account"]
        return any(k in lower_text for k in keys)

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        text = read_text(path, max_pages=2)
        # naive as-of date finder
        asof = None
        for line in text.splitlines():
            if "as of" in line.lower():
                asof = line.split("as of",1)[1].strip().split()[0:3]
                asof = " ".join(asof)
                try:
                    asof = datetime.strptime(asof.replace(",", ""), "%B %d %Y").date()
                except: 
                    asof = None
                break
        # create an umbrella "UBS Consolidated" account for MVP; refine later
        acc = session.query(Account).filter_by(broker_id=broker.id, name="UBS Consolidated").first()
        if not acc:
            acc = Account(broker_id=broker.id, name="UBS Consolidated", base_currency="USD")
            session.add(acc); session.commit()
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=asof)
        session.add(sf); session.commit()
        # placeholder: try to find "Total Portfolio $X"
        total = None
        for line in text.splitlines():
            if "total portfolio" in line.lower() and "$" in line:
                digits = "".join(ch for ch in line if ch.isdigit() or ch in ".")
                try:
                    total = float(digits)
                except: 
                    total = None
                break
        if total:
            session.add(Valuation(date=asof or datetime.today().date(), account_id=acc.id, total_value=total, method="reported"))
            session.commit()
        return {"broker": self.name, "asof": str(asof) if asof else None, "total": total}
