from __future__ import annotations
from datetime import date, datetime
from typing import Iterable, Tuple, List
import math

def _yearfrac(d0: date, d1: date) -> float:
    return (d1 - d0).days / 365.2425

def xnpv(rate: float, cashflows: Iterable[Tuple[date, float]]) -> float:
    cfs = list(cashflows)
    if not cfs:
        return 0.0
    t0 = min(d for d, _ in cfs)
    return sum(cf / ((1 + rate) ** _yearfrac(t0, d)) for d, cf in cfs)

def xirr(cashflows: Iterable[Tuple[date, float]], guess: float = 0.1) -> float | None:
    cfs = list(cashflows)
    if not cfs or all(abs(a) < 1e-12 for _, a in cfs):
        return None
    # Newton with fallback bisection
    r = guess
    for _ in range(50):
        # derivative via finite difference
        f = xnpv(r, cfs)
        if abs(f) < 1e-8:
            return r
        df = (xnpv(r + 1e-6, cfs) - f) / 1e-6
        if abs(df) < 1e-12:
            break
        r -= f / df
        if r <= -0.9999:
            r = -0.9999 + 1e-6
    # bisection in [-0.9999, 10]
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

def time_weighted_return(points: List[Tuple[date, float]], flows: List[Tuple[date, float]] ) -> float | None:
    # Simple TWR across flow breakpoints; flows are external cash flows (investor perspective).
    if not points:
        return None
    points = sorted(points, key=lambda x: x[0])
    flows = sorted(flows, key=lambda x: x[0])
    i = 0
    twr = 1.0
    v0_date, v0 = points[0]
    for v1_date, v1 in points[1:]:
        # sum flows between (v0_date, v1_date]
        f = sum(a for d, a in flows if v0_date < d <= v1_date)
        if v0 == 0:
            return None
        r = (v1 - f) / v0
        twr *= r
        v0_date, v0 = v1_date, v1
    return twr - 1.0
