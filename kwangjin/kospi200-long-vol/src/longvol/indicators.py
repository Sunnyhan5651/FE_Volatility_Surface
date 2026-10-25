"""표본 날짜와 시장 요약용 지표: 근월 ATM IV, 20일 실현변동성."""
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
    """만기가 2개 이상 있는 날만 표본에 넣는다 (kospi200-option-structures 와 같은 날짜 기준)."""
    rows = []
    for d in sorted(smiles):
        order = sorted(smiles[d].values(), key=lambda s: s.days)
        if len(order) < 2:
            continue
        rows.append(dict(date=d, atm_iv=interp(order[0].points, 1.0), rv20=rv.get(d)))
    return rows
