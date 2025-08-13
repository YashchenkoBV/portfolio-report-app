"""Extractor for Freedom Finance broker reports.

Freedom Finance reports are in Russian and contain detailed account
information including the period of the report, net asset values at the
start and end of the period, and tables listing money movements.

We detect the report by looking for the phrases "Отчет брокера" (or
"Отчёт брокера") and "Freedom Finance". The summary extracts the
report period and the net asset values. It also attempts to find
individual external cash flows (deposits and withdrawals) in the text.

When parsing, the end net asset value is stored as a ``Valuation`` and
each external cash flow is stored as a ``CashFlowExternal``. If no
individual flows are found, the flows list will be empty.
"""

from __future__ import annotations

import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from .base import BaseExtractor
from ..bootstrap import (
    bootstrap_broker,
    get_or_create_account,
    parse_date_iso,
    parse_money_to_float,
)
from ...models import SourceFile, Valuation, CashFlowExternal
from ...utils.pdf import read_text_all


class FreedomFinanceExtractor(BaseExtractor):
    name = "Freedom Finance"

    # patterns for period and net asset values
    PERIOD_RX = re.compile(
        r"Отч[её]т брокера за период\s+(\d{4}-\d{2}-\d{2}).*?-\s*(\d{4}-\d{2}-\d{2})",
        re.IGNORECASE | re.DOTALL,
    )
    BEGIN_NAV_RX = re.compile(
        r"Остатки на начало периода.*?Чистые активы.*?(?:USD|US\$).{0,10}([0-9\s.,-]+)",
        re.IGNORECASE | re.DOTALL,
    )
    END_NAV_RX = re.compile(
        r"Остатки на конец периода.*?Чистые активы.*?(?:USD|US\$).{0,10}([0-9\s.,-]+)",
        re.IGNORECASE | re.DOTALL,
    )
    FLOW_LINE_RX = re.compile(r"(Ввод денежных средств|Вывод денежных средств)", re.IGNORECASE)
    DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

    def detect(self, lower_text: str) -> bool:
        return (
            "freedom finance" in lower_text
            and ("отчет брокера" in lower_text or "отчёт брокера" in lower_text)
        )

    def _summarise_text(self, text: str) -> dict:
        mper = self.PERIOD_RX.search(text)
        start_d: date | None = None
        end_d: date | None = None
        if mper:
            start_d = parse_date_iso(mper.group(1))
            end_d = parse_date_iso(mper.group(2))
        begin_nav = None
        end_nav = None
        m0 = self.BEGIN_NAV_RX.search(text)
        m1 = self.END_NAV_RX.search(text)
        if m0:
            begin_nav = parse_money_to_float(m0.group(0))
        if m1:
            end_nav = parse_money_to_float(m1.group(0))
        flows: list[dict] = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if self.FLOW_LINE_RX.search(line):
                # Look at the current line and a few lines around it for a date and a number
                ctx = "\n".join(lines[max(0, i - 2): min(len(lines), i + 3)])
                dmatch = self.DATE_RX.search(ctx)
                amt = parse_money_to_float(ctx)
                if dmatch and amt is not None:
                    dt = parse_date_iso(dmatch.group(0)) or end_d or date.today()
                    if "ввод" in line.lower():
                        amt = -abs(amt)
                    else:
                        amt = abs(amt)
                    flows.append({"date": str(dt), "amount": amt})
        return {
            "broker": self.name,
            "period_start": str(start_d) if start_d else None,
            "period_end": str(end_d) if end_d else None,
            "begin_nav_usd": begin_nav,
            "end_nav_usd": end_nav,
            "flows": flows,
        }

    def summary(self, path: str) -> dict:
        text = read_text_all(path)
        return self._summarise_text(text)

    def parse(self, session: Session, path: str):
        text = read_text_all(path)
        sm = self._summarise_text(text)
        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "FF Account", "USD")
        # record file
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=None)
        session.add(sf)
        session.commit()
        # record valuation at end of period
        if sm["period_end"] and sm["end_nav_usd"] is not None:
            end_date = datetime.strptime(sm["period_end"], "%Y-%m-%d").date()
            session.add(
                Valuation(
                    date=end_date,
                    account_id=acc.id,
                    total_value=sm["end_nav_usd"],
                    method="reported",
                )
            )
        # record cash flows
        for f in sm["flows"]:
            dt = datetime.strptime(f["date"], "%Y-%m-%d").date()
            session.add(
                CashFlowExternal(
                    date=dt,
                    account_id=acc.id,
                    amount=float(f["amount"]),
                    note="External flow",
                )
            )
        session.commit()
        return sm