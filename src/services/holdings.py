"""Holdings aggregation and simple queries.

This module provides functions to compute consolidated metrics such
as the latest total NAV and to retrieve the latest valuation date
per account. These functions operate purely on the database session
without hitting external services.
"""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..models import Valuation


def latest_valuations(session: Session):
    """Return the latest valuation for each account.

    The result is a list of tuples (account_id, date, total_value).
    If an account has multiple valuations on the same date, the latest
    inserted one will be returned. Accounts with no valuations are
    excluded.
    """
    sub = (
        select(Valuation.account_id, func.max(Valuation.date).label("d"))
        .group_by(Valuation.account_id)
        .subquery()
    )
    q = (
        select(Valuation.account_id, Valuation.date, Valuation.total_value)
        .join(sub, (Valuation.account_id == sub.c.account_id) & (Valuation.date == sub.c.d))
    )
    return session.execute(q).all()


def consolidated_nav(session: Session) -> float:
    """Return the sum of the latest total NAV across all accounts."""
    rows = latest_valuations(session)
    return float(sum(r[2] for r in rows))