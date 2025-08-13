# src/services/extractors/freedom_finance.py
from __future__ import annotations
import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from ...models import SourceFile, Valuation, CashFlowExternal
from ...utils.pdf import read_text
from ...services.bootstrap import bootstrap_broker, get_or_create_account, parse_money_to_float, parse_date_iso
from .base import BaseExtractor

PERIOD_RX = re.compile(r"От(ч|чё)т брокера за период.*?(\d{4}-\d{2}-\d{2}).*?-\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE | re.DOTALL)
BEGIN_RX  = re.compile(r"Остатки на начало периода.*?Чистые активы.*?USD\s*([0-9\s.,-]+)", re.IGNORECASE | re.DOTALL)
END_RX    = re.compile(r"Остатки на конец периода.*?Чистые активы.*?USD\s*([0-9\s.,-]+)", re.IGNORECASE | re.DOTALL)
FLOW_RX   = re.compile(r"(Ввод денежных средств|Вывод денежных средств)", re.IGNORECASE)
DATE_RX   = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

class FreedomFinanceExtractor(BaseExtractor):
    name = "Freedom Finance"

    def detect(self, lower_text: str) -> bool:
        return ("freedom finance" in lower_text) and ("отчет брокера" in lower_text or "отчёт брокера" in lower_text)

    def summary(self, path: str) -> dict:
        t = read_text(path, max_pages=12)
        mper = PERIOD_RX.search(t)
        start_d = parse_date_iso(mper.group(2)) if mper else None
        end_d   = parse_date_iso(mper.group(3)) if mper else None
        m0 = BEGIN_RX.search(t)
        m1 = END_RX.search(t)
        begin_nav = parse_money_to_float(m0.group(0)) if m0 else None
        end_nav   = parse_money_to_float(m1.group(0)) if m1 else None

        # quick-and-robust flows (first pass): look for the keyword lines and grab nearby date+amount
        flows = []
        lines = t.splitlines()
        for i, line in enumerate(lines):
            if not FLOW_RX.search(line):
                continue
            ctx = "\n".join(lines[max(0, i-2): min(len(lines), i+3)])
            d = DATE_RX.search(ctx)
            amt = parse_money_to_float(ctx)
            if d and (amt is not None):
                amt = -abs(amt) if "ввод" in line.lower() else abs(amt)
                flows.append({"date": d.group(0), "amount": float(amt), "type": "contribution" if amt < 0 else "withdrawal"})

        return {
            "broker": self.name,
            "period_start": str(start_d) if start_d else None,
            "period_end": str(end_d) if end_d else None,
            "begin_nav_usd": begin_nav,
            "end_nav_usd": end_nav,
            "flows": flows,
        }

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "FF Account", "USD")
        sm = self.summary(path)
        session.add(SourceFile(broker_id=broker.id, path=path, asof_date=None)); session.commit()

        if sm["period_end"] and sm["end_nav_usd"] is not None:
            asof = datetime.strptime(sm["period_end"], "%Y-%m-%d").date()
            session.add(Valuation(date=asof, account_id=acc.id, total_value=sm["end_nav_usd"], method="reported")); session.commit()

        if sm["flows"]:
            for f in sm["flows"]:
                dt = datetime.strptime(f["date"], "%Y-%m-%d").date()
                session.add(CashFlowExternal(date=dt, account_id=acc.id, amount=f["amount"], note=f["type"]))
            session.commit()
        return sm
