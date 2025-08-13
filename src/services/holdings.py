from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..models import Valuation

def latest_valuations(session: Session):
    sub = select(Valuation.account_id, func.max(Valuation.date).label("d")).group_by(Valuation.account_id).subquery()
    q = select(Valuation.account_id, Valuation.date, Valuation.total_value).join(
        sub, (Valuation.account_id == sub.c.account_id) & (Valuation.date == sub.c.d)
    )
    return session.execute(q).all()

def consolidated_nav(session: Session) -> float:
    rows = latest_valuations(session)
    return float(sum(r[2] for r in rows))
