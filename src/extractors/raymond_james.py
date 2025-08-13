from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import SourceFile, Valuation
from ..utils.pdf import read_text_all
from ..services.bootstrap import bootstrap_broker, get_or_create_account, parse_money_to_float
from .base import BaseExtractor

class RaymondJamesExtractor(BaseExtractor):
    name = "Raymond James"

    def detect(self, lower_text: str) -> bool:
        return ("raymond james | client access | my accounts | portfolio" in lower_text) or ("current value" in lower_text)

    def _extract_asof(self, text: str):
        for line in text.splitlines():
            if "as of" in line.lower():
                dt = line.split("as of", 1)[1].strip().split()[0]
                try:
                    return datetime.strptime(dt, "%m/%d/%Y").date()
                except:
                    return None
        return None

    def _extract_total(self, text: str):
        for line in text.splitlines():
            if "current value" in line.lower():
                v = parse_money_to_float(line)
                if v is not None:
                    return v
        return None

    def summary(self, path: str) -> dict:
        t = read_text_all(path)
        asof = self._extract_asof(t)
        return {
            "broker": self.name,
            "asof": str(asof) if asof else None,
            "current_value": self._extract_total(t),
        }

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "RJ Consolidated", "USD")
        sm = self.summary(path)
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=None if sm["asof"] is None else datetime.strptime(sm["asof"], "%Y-%m-%d").date())
        session.add(sf); session.commit()
        if sm["current_value"] is not None:
            asof = datetime.strptime(sm["asof"], "%Y-%m-%d").date() if sm["asof"] else datetime.today().date()
            session.add(Valuation(date=asof, account_id=acc.id, total_value=sm["current_value"], method="reported"))
            session.commit()
        return sm
