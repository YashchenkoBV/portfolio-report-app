from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import Broker, Account, SourceFile, Valuation, CashFlowExternal
from ..services.ingest import bootstrap_broker
from .base import BaseExtractor
from ..utils.pdf import read_text

class FreedomFinanceExtractor(BaseExtractor):
    name = "Freedom Finance"

    def detect(self, lower_text: str) -> bool:
        keys = ["отчет брокера", "freedom finance global plc", "сводная информация по счету"]
        return any(k in lower_text for k in keys)

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        text = read_text(path, max_pages=3)
        # derive period
        start, end = None, None
        for line in text.splitlines():
            if "период" in line.lower() and "—" in line:
                rng = line.split("—")
                start, end = rng[0], rng[1]
                break
        acc = session.query(Account).filter_by(broker_id=broker.id, name="FF Account").first()
        if not acc:
            acc = Account(broker_id=broker.id, name="FF Account", base_currency="USD")
            session.add(acc); session.commit()
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=None)
        session.add(sf); session.commit()
        # naive end NAV detection
        total = None
        for line in text.splitlines():
            if "стоимость портфеля на конец периода" in line.lower():
                digits = "".join(ch for ch in line if ch.isdigit() or ch in ".-")
                try:
                    total = float(digits)
                except:
                    total = None
                break
        if total:
            session.add(Valuation(date=datetime.today().date(), account_id=acc.id, total_value=total, method="reported"))
            session.commit()
        # naive external cash flow parsing (Ввод/Вывод); placeholder for MVP
        for line in text.splitlines():
            if "ввод денежных средств" in line.lower():
                digits = "".join(ch for ch in line if ch.isdigit() or ch in ".-")
                try:
                    amt = float(digits)
                    session.add(CashFlowExternal(date=datetime.today().date(), account_id=acc.id, amount=-abs(amt), note="Ввод (contribution)"))
                except: 
                    pass
            if "вывод денежных средств" in line.lower():
                digits = "".join(ch for ch in line if ch.isdigit() or ch in ".-")
                try:
                    amt = float(digits)
                    session.add(CashFlowExternal(date=datetime.today().date(), account_id=acc.id, amount=abs(amt), note="Вывод (withdrawal)"))
                except: 
                    pass
        session.commit()
        return {"broker": self.name, "period": (start, end), "total": total}
