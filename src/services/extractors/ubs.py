"""Extractor for UBS portfolio PDFs.

This extractor recognises UBS portfolio statements by looking for common
headings such as "Portfolio Holdings" or "Executive Summary". It
extracts the report as‑of date and the total portfolio value. During
parsing, it persists a ``SourceFile`` record and a ``Valuation`` record
for the consolidated account.

Currently this extractor does not parse individual positions. Those could
be added later by reading the "Portfolio Holdings" table.
"""

from __future__ import annotations

import re
from datetime import datetime
from sqlalchemy.orm import Session
from .base import BaseExtractor
from ..bootstrap import (
    bootstrap_broker,
    get_or_create_account,
    parse_date_en,
    parse_money_to_float,
)
from ...models import SourceFile, Valuation
from ...utils.pdf import read_text_all


class UBSExtractor(BaseExtractor):
    name = "UBS"

    # regex for "as of May 27 2025" or similar
    ASOF_RX = re.compile(r"as of\s+([A-Za-z]{3,9} \d{1,2} \d{4})", re.IGNORECASE)

    def detect(self, lower_text: str) -> bool:
        keys = [
            "portfolio holdings",
            "equity summary",
            "asset allocation by account",
            "executive summary",
            "ubs financial services",
            "ubs fs",
        ]
        return any(k in lower_text for k in keys)

    def _extract_asof(self, text: str):
        m = self.ASOF_RX.search(text)
        if m:
            return parse_date_en(m.group(1))
        return None

    def _extract_total(self, text: str):
        total = None
        for line in text.splitlines():
            # look for "Total Portfolio" followed by a number
            if "total portfolio" in line.lower():
                val = parse_money_to_float(line)
                if val is not None:
                    total = val
        return total

    def summary(self, path: str) -> dict:
        text = read_text_all(path)
        asof = self._extract_asof(text)
        total = self._extract_total(text)
        return {
            "broker": self.name,
            "asof": str(asof) if asof else None,
            "total_portfolio": total,
        }

    def parse(self, session: Session, path: str):
        # Read whole PDF to extract numbers
        text = read_text_all(path)
        asof = self._extract_asof(text)
        total = self._extract_total(text)

        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "UBS Consolidated", "USD")
        # record the source file; store asof if present
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=asof)
        session.add(sf)
        session.commit()
        # record valuation if a total was found
        if total is not None:
            session.add(
                Valuation(
                    date=asof or datetime.today().date(),
                    account_id=acc.id,
                    total_value=total,
                    method="reported",
                )
            )
            session.commit()
        return self.summary(path)