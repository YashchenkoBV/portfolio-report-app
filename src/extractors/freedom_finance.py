from __future__ import annotations
import re
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import SourceFile, Valuation, CashFlowExternal
from ..utils.pdf import read_text_all
from ..services.bootstrap import bootstrap_broker, get_or_create_account, parse_money_to_float, parse_date_iso
from .base import BaseExtractor

PERIOD_RX = re.compile(r"Отчет брокера за период\s+(\d{4}-\d{2}-\d{2}).*?-\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE | re.DOTALL)
BEGIN_NAV_RX = re.compile(r"Остатки на начало периода.*?Чистые активы,\s*USD\s*([0-9\s.,-]+)", re.IGNORECASE | re.DOTALL)
END_NAV_RX   = re.compile(r"Остатки на конец периода.*?Чистые активы,\s*USD\s*([0-9\s.,-]+)", re.IGNORECASE | re.DOTALL)
MONEY_MOVES_SUMMARY_RX = re.compile(r"Движение денег.*?USD\s+[0-9\s.,-]+\s+[0-9\s.,-]+\s+([0-9\s.,-]+)\s+[0-9\s.,-]+", re.IGNORECASE | re.DOTALL)
FLOW_LINE_RX = re.compile(r"(Ввод денежных средств|Вывод денежных средств)", re.IGNORECASE)
DATE_NEAR_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

class FreedomFinanceExtractor(BaseExtractor):
    name = "Freedom Finance"

    def detect(self, lower_text: str) -> bool:
        return ("отчет брокера за период" in lower_text) and ("freedom finance global plc" in lower_text)

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "FF Account", "USD")

        text = read_text_all(path)
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=None)
        session.add(sf); session.commit()

        # Period
        mper = PERIOD_RX.search(text)
        period = (None, None)
        if mper:
            start_d = parse_date_iso(mper.group(1))
            end_d = parse_date_iso(mper.group(2))
            period = (start_d, end_d)

        # Begin/End NAV
        m0 = BEGIN_NAV_RX.search(text)
        m1 = END_NAV_RX.search(text)
        begin_nav = parse_money_to_float(m0.group(0)) if m0 else None
        end_nav   = parse_money_to_float(m1.group(0)) if m1 else None

        # Save end valuation if available
        if period[1] and end_nav:
            session.add(Valuation(date=period[1], account_id=acc.id, total_value=end_nav, method="reported"))
            session.commit()

        # Try to read summary net flows from "Движение денег" table row USD (3rd numeric = Вводы/выводы)
        # Example row in your file shows net flows present on that line. :contentReference[oaicite:6]{index=6}
        msum = MONEY_MOVES_SUMMARY_RX.search(text)
        if msum:
            net_flows = parse_money_to_float(msum.group(0))
        else:
            net_flows = None

        # Extract discrete external flows (first pass): look for lines with the keywords, then capture nearby ISO date and amount
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if FLOW_LINE_RX.search(line):
                context = "\n".join(lines[max(0, i-2): min(len(lines), i+3)])
                # find date near
                d = DATE_NEAR_RX.search(context)
                # find money near
                amt = parse_money_to_float(context)
                if d and amt:
                    # Investor perspective: contribution negative, withdrawal positive
                    if "ввод" in line.lower():
                        amount = -abs(amt)
                    else:
                        amount = abs(amt)
                    dt = parse_date_iso(d.group(0)) or (period[1] or datetime.today().date())
                    session.add(CashFlowExternal(date=dt, account_id=acc.id, amount=amount, note=line.strip()))

        session.commit()

        # If we found no discrete flows but we have a net summary + period, drop a single net at period midpoint (approximation)
        q = session.query(CashFlowExternal).filter(CashFlowExternal.account_id == acc.id).count()
        if q == 0 and net_flows and all(period):
            mid = period[0] + (period[1] - period[0]) / 2
            session.add(CashFlowExternal(date=mid, account_id=acc.id, amount=net_flows, note="Net external flows (summary)"))
            session.commit()

        return {
            "broker": self.name,
            "period": (str(period[0]) if period[0] else None, str(period[1]) if period[1] else None),
            "begin_nav": begin_nav,
            "end_nav": end_nav,
            "flows_detected": int(session.query(CashFlowExternal).filter(CashFlowExternal.account_id == acc.id).count()),
        }
