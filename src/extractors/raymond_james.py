from __future__ import annotations
import re
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import SourceFile, Valuation
from ..utils.pdf import read_text_all
from ..services.bootstrap import bootstrap_broker, get_or_create_account, parse_money_to_float
from .base import BaseExtractor

ASOF_RX = re.compile(r"As of\s+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)

class RaymondJamesExtractor(BaseExtractor):
    name = "Raymond James"

    def detect(self, lower_text: str) -> bool:
        return "raymond james | client access | my accounts | portfolio" in lower_text or "current value" in lower_text

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "RJ Consolidated", "USD")

        text = read_text_all(path)
        asof = None
        for line in text.splitlines():
            if "as of" in line.lower():
                # Raymond James prints US format “As of 07/23/2025”
                dt = line.split("As of", 1)[1].strip().split()[0]
                try:
                    asof = datetime.strptime(dt, "%m/%d/%Y").date()
                except:
                    asof = None
                break

        total = None
        for line in text.splitlines():
            if "current value" in line.lower():
                val = parse_money_to_float(line)
                if val:
                    total = val
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=asof)
        session.add(sf); session.commit()

        if total:
            session.add(Valuation(date=asof or datetime.today().date(), account_id=acc.id, total_value=total, method="reported"))
            session.commit()
        return {"broker": self.name, "asof": str(asof) if asof else None, "total": total}
