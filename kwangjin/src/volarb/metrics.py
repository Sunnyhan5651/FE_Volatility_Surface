"""성과 지표."""
from __future__ import annotations

import math
import statistics as st

from .config import TRADING_DAYS


def drawdown_series(equity):
    """누적 손익 곡선의 고점 대비 낙폭 (≤ 0)."""
    peak, out = equity[0], []
    for e in equity:
        peak = max(peak, e)
        out.append(e - peak)
    return out


def max_drawdown_duration(equity) -> int:
    """고점 갱신 없이 지난 최장 거래일 수."""
    peak, since, longest = equity[0], 0, 0
    for e in equity:
        if e >= peak:
            peak, since = e, 0
        else:
            since += 1
            longest = max(longest, since)
    return longest


def compute_metrics(equity, trades, detail=None) -> dict:
    """모든 수익률 단위는 %. 수익률은 거래별 진입 선물가 기준 가산(additive) 누적."""
    rets = [equity[i] - equity[i - 1] for i in range(1, len(equity))]
    total = equity[-1] - equity[0]
    ann_vol = st.pstdev(rets) * math.sqrt(TRADING_DAYS) if len(set(rets)) > 1 else 0.0
    years = len(equity) / TRADING_DAYS
    ann_ret = total / years if years > 0 else 0.0
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")
    mdd = min(drawdown_series(equity))
    eff = [t for t in trades if abs(t) > 1e-9]
    wins, losses = [t for t in eff if t > 0], [t for t in eff if t < 0]
    holds = [d[4] for d in detail] if detail else []
    return dict(
        total_return_pct=100 * total,
        ann_return_pct=100 * ann_ret,
        ann_vol_pct=100 * ann_vol,
        sharpe=sharpe,
        mdd_pct=100 * mdd,
        mdd_days=max_drawdown_duration(equity),
        calmar=(ann_ret / abs(mdd)) if mdd < 0 else float("nan"),
        n_trades=len(trades),
        effective_trades=len(eff),
        win_rate_pct=(100 * len(wins) / len(eff)) if eff else float("nan"),
        avg_trade_pct=(100 * st.mean(eff)) if eff else float("nan"),
        best_trade_pct=(100 * max(eff)) if eff else float("nan"),
        worst_trade_pct=(100 * min(eff)) if eff else float("nan"),
        profit_factor=(sum(wins) / abs(sum(losses))) if losses else float("nan"),
        avg_hold_days=(st.mean(holds) if holds else float("nan")),
    )


def newey_west_t(x, lag: int = 5):
    """평균의 Newey-West HAC t값. (평균, t) 반환."""
    n = len(x)
    m = sum(x) / n
    xc = [a - m for a in x]
    gamma = lambda k: sum(xc[i] * xc[i - k] for i in range(k, n)) / n
    var = gamma(0) + 2 * sum((1 - k / (lag + 1)) * gamma(k) for k in range(1, lag + 1))
    return m, (m / math.sqrt(var / n)) if var > 0 else float("nan")
