"""성과 지표."""
from __future__ import annotations

import math
import statistics as st


def nw_t(x, lags=None):
    """평균에 대한 Newey-West t (Bartlett 커널, 기본 시차 = floor(4(n/100)^(2/9)))."""
    n = len(x)
    if n < 3:
        return float("nan")
    mu = sum(x) / n
    e = [v - mu for v in x]
    L = lags if lags is not None else int(4 * (n / 100) ** (2 / 9))
    var = sum(v * v for v in e) / n
    for l in range(1, L + 1):
        var += 2 * (1 - l / (L + 1)) * sum(e[t] * e[t - l] for t in range(l, n)) / n
    return mu / math.sqrt(var / n) if var > 0 else float("nan")


def cumulative(xs):
    out, s = [], 0.0
    for x in xs:
        s += x
        out.append(s)
    return out


def max_drawdown(curve):
    """잔고 기준 최대 낙폭 (음수, 비율).
    자본 1(진입 선물가 명목 1단위)에서 시작해 누적손익을 단순 합산한 잔고 1 + curve 를 쓰고,
    MDD = min(잔고 / 직전 최고 잔고 − 1)."""
    peak, m = 1.0, 0.0
    for v in curve:
        eq = 1.0 + v
        peak = max(peak, eq)
        m = min(m, eq / peak - 1.0)
    return m


def summarize(dates, daily, trades):
    """일별손익 dict 와 [Trade] → 지표 dict (수익률 단위 %)."""
    x = [daily.get(d, 0.0) for d in dates]
    curve = cumulative(x)
    sd = st.pstdev(x)
    nan = float("nan")
    return dict(
        누적수익률=100 * curve[-1],
        Sharpe=(st.mean(x) * 252) / (sd * math.sqrt(252)) if sd > 0 else nan,
        MDD=100 * max_drawdown(curve),
        롤당평균=100 * st.mean(t.pnl for t in trades) if trades else nan,
        승률=100 * sum(t.pnl > 0 for t in trades) / len(trades) if trades else nan,
        롤횟수=len(trades),
        대체평가=100 * sum(t.fallback for t in trades) / max(1, sum(t.held for t in trades)),
        NW_t=nw_t(x),
        curve=[100 * v for v in curve],
    )
