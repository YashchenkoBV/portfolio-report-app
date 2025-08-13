from __future__ import annotations
import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from ..models import SourceFile, Valuation, CashFlowExternal
from ..utils.pdf import read_text_all
from ..services.bootstrap import (
    bootstrap_broker, get_or_create_account,
    parse_money_to_float, parse_date_iso, midpoint
)
from .base import BaseExtractor

PERIOD_RX = re.compile(r"От(ч|чё)т брокера за период\s+(\d{4}-\d{2}-\d{2}).*?-\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE | re.DOTALL)
BEGIN_NAV_RX = re.compile(r"Остатки на начало периода.*?Чистые активы.*?USD.*?([0-9\s.,-]+)", re.IGNORECASE | re.DOTALL)
END_NAV_RX   = re.compile(r"Остатки на конец периода.*?Чистые активы.*?USD.*?([0-9\s.,-]+)", re.IGNORECASE | re.DOTALL)
FLOW_LINE_RX = re.compile(r"(Ввод денежных средств|Вывод денежных средств)", re.IGNORECASE)
DATE_RX      = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
MONEY_RX     = re.compile(r"[-+]?\s*(?:USD|US\$|\$)?\s*(?:\d{1,3}(?:[ ,]?\d{3})+|\d+)(?:\.\d+)?")

class FreedomFinanceExtractor(BaseExtractor):
    name = "Freedom Finance"

    def detect(self, lower_text: str) -> bool:
        return ("freedom finance global plc" in lower_text) and ("отчет брокера" in lower_text or "отчёт брокера" in lower_text)

    def _summarize_text(self, text: str) -> dict:
        mper = PERIOD_RX.search(text)
        start_d, end_d = None, None
        if mper:
            start_d = parse_date_iso(mper.group(2))
            end_d   = parse_date_iso(mper.group(3))
        m0 = BEGIN_NAV_RX.search(text)
        m1 = END_NAV_RX.search(text)
        begin_nav = parse_money_to_float(m0.group(0)) if m0 else None
        end_nav   = parse_money_to_float(m1.group(0)) if m1 else None

        flows = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if FLOW_LINE_RX.search(line):
                ctx = "\n".join(lines[max(0, i-2): min(len(lines), i+3)])
                d = DATE_RX.search(ctx)
                mv = None
                # try closest money on same or next line block
                for block in [line, ctx]:
                    val = parse_money_to_float(block)
                    if val is not None:
                        mv = val; break
                if d and mv is not None:
                    dt = parse_date_iso(d.group(0)) or end_d or date.today()
                    amt = -abs(mv) if "ввод" in line.lower() else abs(mv)
                    flows.append({"date": str(dt), "amount": amt, "type": "contribution" if amt < 0 else "withdrawal"})
        return {
            "broker": self.name,
            "period_start": str(start_d) if start_d else None,
            "period_end": str(end_d) if end_d else None,
            "begin_nav_usd": begin_nav,
            "end_nav_usd": end_nav,
            "flows": flows,
        }

    def summary(self, path: str) -> dict:
        return self._summarize_text(read_text_all(path))

    def parse(self, session: Session, path: str):
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "FF Account", "USD")
        sm = self.summary(path)

        sf = SourceFile(broker_id=broker.id, path=path, asof_date=None)
        session.add(sf); session.commit()

        if sm["period_end"] and sm["end_nav_usd"] is not None:
            asof = datetime.strptime(sm["period_end"], "%Y-%m-%d").date()
            session.add(Valuation(date=asof, account_id=acc.id, total_value=sm["end_nav_usd"], method="reported"))
            session.commit()

        # persist external flows (discrete)
        if sm["flows"]:
            for f in sm["flows"]:
                dt = datetime.strptime(f["date"], "%Y-%m-%d").date()
                session.add(CashFlowExternal(date=dt, account_id=acc.id, amount=float(f["amount"]), note=f["type"]))
            session.commit()
        else:
            # fallback: if begin/end exist, drop net at midpoint (approximation)
            if sm["begin_nav_usd"] is not None and sm["end_nav_usd"] is not None and sm["period_start"] and sm["period_end"]:
                d0 = datetime.strptime(sm["period_start"], "%Y-%m-%d").date()
                d1 = datetime.strptime(sm["period_end"], "%Y-%m-%d").date()
                mid = midpoint(d0, d1)
                # net flow ≈ End - Start - P&L ; with no P&L, we can’t infer; skip to avoid misleading data
                # leave as no-op; flows will be picked up when discrete lines are parsed correctly
                pass

        return sm
