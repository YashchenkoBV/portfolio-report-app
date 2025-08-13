"""Functions to compute financial key performance indicators.

This module provides implementations of XNPV, XIRR and time weighted
returns. These functions operate on sequences of (date, amount) tuples
representing cash flows. See the assignment description for sign
conventions: contributions are negative and withdrawals positive. To
compute a money weighted return, append the terminal value as a
positive cash flow at the end of the sequence.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Tuple, List


def _yearfrac(d0: date, d1: date) -> float:
    """Return the fraction of a year between two dates using 365.2425 days."""
    return (d1 - d0).days / 365.2425


def xnpv(rate: float, cashflows: Iterable[Tuple[date, float]]) -> float:
    """Calculate the net present value of a series of cash flows at a given rate."""
    cfs = list(cashflows)
    if not cfs:
        return 0.0
    t0 = min(d for d, _ in cfs)
    return sum(cf / ((1 + rate) ** _yearfrac(t0, d)) for d, cf in cfs)


def xirr(cashflows: Iterable[Tuple[date, float]], guess: float = 0.1) -> float | None:
    """Compute the internal rate of return for a series of cash flows.

    Uses Newton's method with a bisection fallback to find the rate such
    that the net present value is zero. Returns None if no root can be
    bracketed. A maximum of 50 Newton iterations and 200 bisection
    iterations are attempted.
    """
    cfs = list(cashflows)
    if not cfs or all(abs(a) < 1e-12 for _, a in cfs):
        return None
    r = guess
    # Newton iteration
    for _ in range(50):
        f = xnpv(r, cfs)
        if abs(f) < 1e-8:
            return r
        # derivative by finite difference
        df = (xnpv(r + 1e-6, cfs) - f) / 1e-6
        if abs(df) < 1e-12:
            break
        r -= f / df
        if r <= -0.9999:
            r = -0.9998
    # Bisection fallback
    lo, hi = -0.9999, 10.0
    flo, fhi = xnpv(lo, cfs), xnpv(hi, cfs)
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = xnpv(mid, cfs)
        if abs(fm) < 1e-8:
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def nav_bridge(start_nav: float, end_nav: float, contributions: float, withdrawals: float) -> dict:
    """Return a breakdown of the change in NAV between two dates.

    The net flows are contributions minus withdrawals. The P&L is computed
    as end_nav minus start_nav minus net flows. The returned dictionary
    includes each component and the start and end NAV.
    """
    net_flows = contributions - withdrawals
    pnl = end_nav - start_nav - net_flows
    return {
        "start_nav": start_nav,
        "contributions": contributions,
        "withdrawals": withdrawals,
        "net_flows": net_flows,
        "pnl": pnl,
        "end_nav": end_nav,
    }


def time_weighted_return(
    points: List[Tuple[date, float]],
    flows: List[Tuple[date, float]],
) -> float | None:
    """Compute a simple time weighted return given valuation points and flows.

    The list of ``points`` should be sorted by date. Each point is a
    tuple of (date, value). The list of ``flows`` is a list of external
    cash flows (date, amount). Positive amounts are withdrawals and
    negative amounts are contributions. The function returns the
    compounded growth rate minus one.
    """
    if not points or len(points) < 2:
        return None
    points = sorted(points, key=lambda x: x[0])
    flows = sorted(flows, key=lambda x: x[0])
    twr_factor = 1.0
    v0_date, v0 = points[0]
    for v1_date, v1 in points[1:]:
        # sum flows between v0_date (exclusive) and v1_date (inclusive)
        f = sum(a for d, a in flows if v0_date < d <= v1_date)
        if v0 == 0:
            return None
        subperiod = (v1 - f) / v0
        twr_factor *= subperiod
        v0_date, v0 = v1_date, v1
    return twr_factor - 1.0