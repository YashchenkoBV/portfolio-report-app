"""Extractor for Raymond James portfolio PDFs.

This extractor recognises Raymond James client access statements. It
extracts the statement date ("As of" line) and the current value of the
portfolio. The as‑of date uses the US month/day/year format.

Currently individual positions are not parsed. That could be added by
extracting the holdings table from the document.
"""

from __future__ import annotations

import re
from datetime import datetime
from sqlalchemy.orm import Session
from .base import BaseExtractor
from ..bootstrap import (
    bootstrap_broker,
    get_or_create_account,
    parse_money_to_float,
)
from ...models import SourceFile, Valuation
from ...utils.pdf import read_text_all


class RaymondJamesExtractor(BaseExtractor):
    name = "Raymond James"

    def detect(self, lower_text: str) -> bool:
        return (
            "raymond james" in lower_text
            and "portfolio" in lower_text
        ) or ("current value" in lower_text)

    def _extract_asof(self, text: str):
        for line in text.splitlines():
            if "as of" in line.lower():
                # Expect format "As of 07/23/2025"
                dt = line.split("as of", 1)[1].strip().split()[0]
                try:
                    return datetime.strptime(dt, "%m/%d/%Y").date()
                except Exception:
                    return None
        return None

    def _extract_total(self, text: str):
        for line in text.splitlines():
            if "current value" in line.lower():
                val = parse_money_to_float(line)
                if val is not None:
                    return val
        return None

    def summary(self, path: str) -> dict:
        text = read_text_all(path)
        asof = self._extract_asof(text)
        total = self._extract_total(text)
        return {
            "broker": self.name,
            "asof": str(asof) if asof else None,
            "current_value": total,
        }

    def parse(self, session: Session, path: str):
        text = read_text_all(path)
        asof = self._extract_asof(text)
        total = self._extract_total(text)

        broker = bootstrap_broker(session, self.name)
        acc = get_or_create_account(session, broker.id, "RJ Consolidated", "USD")
        # record source file
        sf = SourceFile(broker_id=broker.id, path=path, asof_date=asof)
        session.add(sf)
        session.commit()
        # record valuation
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