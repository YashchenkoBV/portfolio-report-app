from __future__ import annotations
import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from ..models import Broker, Account

_MONEY_RX = re.compile(r"[-+]?\$?\s*([0-9]{1,3}(?:[, ]?[0-9]{3})*(?:\.[0-9]{1,2})|[0-9]+(?:\.[0-9]{1,2}))")

def bootstrap_broker(session: Session, name: str) -> Broker:
    b = session.query(Broker).filter_by(name=name).first()
    if not b:
        b = Broker(name=name)
        session.add(b)
        session.commit()
    return b

def get_or_create_account(session: Session, broker_id: int, name: str, currency: str = "USD") -> Account:
    acc = session.query(Account).filter_by(broker_id=broker_id, name=name).first()
    if not acc:
        acc = Account(broker_id=broker_id, name=name, base_currency=currency)
        session.add(acc)
        session.commit()
    return acc

def parse_money_to_float(s: str) -> float | None:
    # Accept "$13,072,114.79", "13 072 114.79", "3,015,488.43", "-1,234.56"
    m = _MONEY_RX.search(s.replace("\u00A0"," ").replace(" "," "))
    if not m:
        return None
    raw = m.group(1).replace(",", "").replace(" ", "")
    return float(raw)

def parse_date_en(s: str) -> date | None:
    # e.g. "as of May 27, 2025"
    s = s.replace(",", " ")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except:
            pass
    return None

def parse_date_iso(s: str) -> date | None:
    # e.g. "2025-03-27"
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except:
        return None
