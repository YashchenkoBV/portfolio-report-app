from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..models import Valuation, Account

def latest_valuations(session: Session):
    sub = select(Valuation.account_id, func.max(Valuation.date).label("d")).group_by(Valuation.account_id).subquery()
    q = select(Valuation.account_id, Valuation.date, Valuation.total_value).join(
        sub, (Valuation.account_id == sub.c.account_id) & (Valuation.date == sub.c.d)
    )
    return session.execute(q).all()

def consolidated_nav(session: Session) -> float:
    rows = latest_valuations(session)
    return float(sum(r[2] for r in rows))

def all_valuations(session: Session):
    q = select(Valuation.date, func.sum(Valuation.total_value)).group_by(Valuation.date).order_by(Valuation.date)
    return [(d, float(v)) for d, v in session.execute(q).all()]

def account_names(session: Session):
    return {a.id: a.name for a in session.query(Account).all()}
