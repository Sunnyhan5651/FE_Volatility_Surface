"""신호용 지표: 근월 ATM IV, 20일 실현변동성, VRP, rolling z-score."""
from __future__ import annotations

import math
import statistics as st

from .pricing import interp


def realized_vol(spot, window=20):
    """연율화 실현변동성(%) {날짜: RV}. 해당 날짜까지의 수익률만 사용."""
    rets = [(spot[i][0], math.log(spot[i][1] / spot[i - 1][1])) for i in range(1, len(spot))]
    out = {}
    for i in range(window - 1, len(rets)):
        w = [r for _, r in rets[i - window + 1:i + 1]]
        out[rets[i][0]] = st.pstdev(w) * math.sqrt(252) * 100
    return out


def indicator_rows(smiles, rv):
    """만기가 2개 이상 있는 날만 표본에 넣는다 (기존 레포와 같은 날짜 기준)."""
    rows = []
    for d in sorted(smiles):
        order = sorted(smiles[d].values(), key=lambda s: s.days)
        if len(order) < 2:
            continue
        atm = interp(order[0].points, 1.0)
        r = rv.get(d)
        rows.append(dict(date=d, atm_iv=atm, rv20=r,
                         vrp=(atm - r) if (atm is not None and r is not None) else None))
    return rows


def rolling_z(vals, window):
    """과거 window 개 값(당일 제외)의 평균·표준편차로 당일 값을 표준화. 선견편향 없음."""
    z = [None] * len(vals)
    for i, v in enumerate(vals):
        if v is None:
            continue
        hist = [x for x in vals[max(0, i - window):i] if x is not None]
        if len(hist) < max(10, window // 2):
            continue
        mu, sd = st.mean(hist), st.pstdev(hist)
        if sd > 0:
            z[i] = (v - mu) / sd
    return z
