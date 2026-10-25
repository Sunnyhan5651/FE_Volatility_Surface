"""성과 지표. 각 전략은 여러 셀(파라미터 조합)의 일별 손익을 평균한 곡선으로 평가한다."""
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
    """누적손익 곡선(0에서 시작한다고 보고)의 고점 대비 최대 낙폭 (음수)."""
    peak, m = 0.0, 0.0
    for v in curve:
        peak = max(peak, v)
        m = min(m, v - peak)
    return m


def summarize(dates, cells):
    """cells: [(일별손익 dict, [Trade]), ...] → 지표 dict (수익률 단위 %)."""
    k = len(cells)
    avg = [sum(c[0].get(d, 0.0) for c in cells) / k for d in dates]
    curve = cumulative(avg)
    sd = st.pstdev(avg)
    worst = min(max_drawdown(cumulative([c[0].get(d, 0.0) for d in dates])) for c in cells)
    eff = [t for c in cells for t in c[1] if abs(t.pnl) > 1e-12]
    nan = float("nan")
    return dict(
        누적수익률=100 * curve[-1],
        Sharpe=(st.mean(avg) * 252) / (sd * math.sqrt(252)) if sd > 0 else nan,
        MDD=100 * max_drawdown(curve),
        최악셀MDD=100 * worst,
        거래당평균=100 * st.mean(t.pnl for t in eff) if eff else nan,
        승률=100 * sum(t.pnl > 0 for t in eff) / len(eff) if eff else nan,
        거래수=len(eff) / k,
        매도비중=100 * sum(t.sign < 0 for t in eff) / len(eff) if eff else nan,
        대체평가=100 * sum(t.fallback for t in eff) / max(1, sum(t.held for t in eff)),
        NW_t=nw_t(avg),
        curve=[100 * v for v in curve],
    )
