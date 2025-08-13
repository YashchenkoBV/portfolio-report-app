from __future__ import annotations
import re
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from ..models import Broker, Account

# captures sign + number; commas/spaces optional
_MONEY_RX = re.compile(r"(?P<sgn>[-+])?\s*\$?\s*(?P<num>(?:\d{1,3}(?:[ ,]?\d{3})+|\d+)(?:\.\d+)?)")

def bootstrap_broker(session: Session, name: str) -> Broker:
    b = session.query(Broker).filter_by(name=name).first()
    if not b:
        b = Broker(name=name)
        session.add(b); session.commit()
    return b

def get_or_create_account(session: Session, broker_id: int, name: str, currency: str = "USD") -> Account:
    acc = session.query(Account).filter_by(broker_id=broker_id, name=name).first()
    if not acc:
        acc = Account(broker_id=broker_id, name=name, base_currency=currency)
        session.add(acc); session.commit()
    return acc

def parse_money_to_float(s: str) -> float | None:
    m = _MONEY_RX.search(s.replace("\u00A0", " "))
    if not m:
        return None
    raw = m.group("num").replace(",", "").replace(" ", "")
    val = float(raw)
    if m.group("sgn") == "-":
        val = -val
    return val

def parse_date_en(s: str) -> date | None:
    s = s.replace(",", " ")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except:
            pass
    return None

def parse_date_iso(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except:
        return None

def midpoint(d0: date, d1: date) -> date:
    delta = d1 - d0
    return d0 + (delta // 2)  # integer half-day resolution
