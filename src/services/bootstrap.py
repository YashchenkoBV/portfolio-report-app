"""Bootstrap helpers for extractors.

This module provides small helper functions used across extractors:
  * ``bootstrap_broker``: get or create a broker record.
  * ``get_or_create_account``: get or create an account.
  * ``parse_money_to_float``: parse a monetary string with optional sign.
  * ``parse_date_en`` and ``parse_date_iso``: parse English and ISO dates.
  * ``midpoint``: compute the midpoint date between two dates.

These utilities live in a separate module to avoid circular imports between
extractors and the ingestion service.
"""

from __future__ import annotations

import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from ..models import Broker, Account

# Regex to match optional sign and a number containing digits, spaces or commas.
_MONEY_RX = re.compile(r"(?P<sgn>[-+])?\s*\$?\s*(?P<num>(?:\d{1,3}(?:[ ,]?\d{3})+|\d+)(?:\.\d+)?)")


def bootstrap_broker(session: Session, name: str) -> Broker:
    """Return an existing broker by name or create it."""
    broker = session.query(Broker).filter(Broker.name == name).first()
    if not broker:
        broker = Broker(name=name)
        session.add(broker)
        session.commit()
    return broker


def get_or_create_account(session: Session, broker_id: int, name: str, currency: str = "USD") -> Account:
    """Return an existing account or create a new one if necessary."""
    acc = (
        session.query(Account)
        .filter(Account.broker_id == broker_id, Account.name == name)
        .first()
    )
    if not acc:
        acc = Account(broker_id=broker_id, name=name, base_currency=currency)
        session.add(acc)
        session.commit()
    return acc


def parse_money_to_float(s: str) -> float | None:
    """Parse a monetary string into a float.

    Examples
    --------
    ``$1,234.56`` → 1234.56
    ``- 2 000`` → -2000.0
    ``+3,000`` → 3000.0

    Returns None if no number is found.
    """
    m = _MONEY_RX.search(s.replace("\u00A0", " "))
    if not m:
        return None
    raw = m.group("num").replace(",", "").replace(" ", "")
    val = float(raw)
    if m.group("sgn") == "-":
        val = -val
    return val


def parse_date_en(s: str) -> date | None:
    """Parse an English date string of the form 'May 27 2025' or 'May 27, 2025'."""
    s = s.replace(",", " ")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            continue
    return None


def parse_date_iso(s: str) -> date | None:
    """Parse an ISO date string of the form YYYY-MM-DD."""
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def midpoint(d0: date, d1: date) -> date:
    """Return the midpoint date between two dates (rounded down)."""
    delta = d1 - d0
    return d0 + (delta // 2)