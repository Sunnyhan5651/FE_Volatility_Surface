"""백테스트 엔진: 신호 진입 → 일별 마크 → 청산, 일별 손익 누적.

회계
  - 손익 = (옵션 평가 − 진입가) + 누적 헤지 손익
  - 체결 비용: 매수 레그는 IV + cost_iv_pt, 매도 레그는 IV − cost_iv_pt
  - 단위: 선물가 기준 수익률 (base = 진입 시 선물가)
  - 매일 델타 재헤지 (rehedge=True)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from .config import RISK_FREE, Params
from .data import interpolate
from .pricing import bs76


@dataclass
class BacktestResult:
    daily:  Dict[str, float] = field(default_factory=dict)   # date -> 수익률 증분
    trades: List[float]      = field(default_factory=list)   # 거래별 수익률
    detail: List[tuple]      = field(default_factory=list)   # (진입일, 청산일, 태그, 수익률, 보유일)


def _price_legs(legs, day_smiles, mode: str, cost_iv_pt: float):
    """레그들을 평가. mode: 'mid'|'entry'|'exit'.
    반환: (총가치, {expiry: 델타}, {expiry: 선물가}) 또는 None.
    """
    value, deltas, fwds = 0.0, defaultdict(float), {}
    for leg in legs:
        sm = day_smiles.get(leg["expiry"])
        if sm is None:
            return None
        F, T = sm.forward, sm.days / 365
        if T <= 0:
            return None
        iv = interpolate(sm.points, leg["K"] / F)
        if iv is None:
            return None
        if mode == "entry":
            iv += cost_iv_pt * (1 if leg["qty"] > 0 else -1)
        elif mode == "exit":
            iv -= cost_iv_pt * (1 if leg["qty"] > 0 else -1)
        price, delta, _ = bs76(F, leg["K"], T, max(iv, 1.0) / 100, RISK_FREE, leg["right"])
        value += leg["qty"] * price
        deltas[leg["expiry"]] += leg["qty"] * delta
        fwds[leg["expiry"]] = F
    return value, deltas, fwds


def run_engine(dates, rows_by_date, z, smiles_by_day,
               builder: Callable, p: Params) -> BacktestResult:
    daily, trades, detail = defaultdict(float), [], []
    n, i = len(dates), 0
    while i < n:
        if z[i] is None or abs(z[i]) < p.z_entry:
            i += 1
            continue
        sig_i, i = i, i + p.entry_lag
        if i >= n:
            break
        day0  = dates[i]
        built = builder(z[sig_i], rows_by_date[day0], smiles_by_day[day0])
        if built is None:
            i = sig_i + 1
            continue
        legs, base, tag = built
        ent = _price_legs(legs, smiles_by_day[day0], "entry", p.cost_iv_pt)
        if ent is None:
            i = sig_i + 1
            continue
        v_entry, d0, prev_f = ent
        hedge = {e: -d for e, d in d0.items()}
        cum_hedge, prev_total, prev_exit_adj = 0.0, 0.0, 0.0
        last_day, j, exited = day0, i, False
        while j + 1 < n and (j - i) < p.max_hold:
            j += 1
            dj  = dates[j]
            mid = _price_legs(legs, smiles_by_day[dj], "mid", p.cost_iv_pt)
            if mid is None:
                daily[last_day] += prev_exit_adj / base
                prev_total += prev_exit_adj
                exited = True
                j -= 1
                break
            v_mid, deltas, fs = mid
            cum_hedge += sum(hedge[e] * (fs[e] - prev_f[e]) for e in hedge)
            total_mid  = v_mid - v_entry + cum_hedge
            zj = z[j]
            stopped = (
                p.stop_dz is not None and zj is not None and z[sig_i] is not None
                and (zj if z[sig_i] > 0 else -zj) >= abs(z[sig_i]) + p.stop_dz
            )
            if (zj is not None and abs(zj) < p.z_exit) or (j - i) >= p.max_hold or stopped:
                ex    = _price_legs(legs, smiles_by_day[dj], "exit", p.cost_iv_pt)
                v_ex  = ex[0] if ex else v_mid
                total = v_ex - v_entry + cum_hedge
                daily[dj] += (total - prev_total) / base
                prev_total = total
                exited = True
                break
            daily[dj]      += (total_mid - prev_total) / base
            prev_total       = total_mid
            ex               = _price_legs(legs, smiles_by_day[dj], "exit", p.cost_iv_pt)
            prev_exit_adj    = (ex[0] - v_mid) if ex else 0.0
            last_day, prev_f = dj, fs
            if p.rehedge:
                hedge = {e: -d for e, d in deltas.items()}
        if not exited:
            daily[last_day] += prev_exit_adj / base
            prev_total      += prev_exit_adj
        trades.append(prev_total / base)
        detail.append((day0, dates[min(j, n - 1)], tag, prev_total / base, j - i))
        i = j + 1
    return BacktestResult(dict(daily), trades, detail)


def to_equity(dates, daily: Dict[str, float]) -> List[float]:
    """누적 손익 곡선 (길이 len(dates)+1, 첫 값 0)."""
    eq = [0.0]
    for d in dates:
        eq.append(eq[-1] + daily.get(d, 0.0))
    return eq
