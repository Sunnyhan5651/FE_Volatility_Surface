"""백테스트 엔진: 신호 진입 → 일별 마크 → 청산, 일별 손익 누적.

회계 원칙
  * 손익 = (옵션 평가액 − 진입가) + 누적 헤지손익 − 선물 거래비용.
    진입가에는 매수 +IV / 매도 −IV 비용이 반영된다.
  * 청산 평가액에도 불리한 방향의 비용을 반영한다 (진입·청산 각각 레그당 cost_iv_pt).
  * 헤지 선물은 거래한 수량 × fut_cost (지수 포인트) 를 비용으로 뺀다 (진입 헤지·매일 재헤지·청산 때 해제).
  * 한 번에 하나의 포지션만 보유하고, 일별 손익은 진입 시점 선물가(base)로 나눠 수익률화한다.
  * 일별 재헤지: 전일 종가 기준 델타로 헤지한 선물이 당일 가격변화만큼 손익을 낸다.

보유 중 평가 (5년 판에서 바꾼 부분)
  * 행사가가 그날 스마일 밖으로 나가 보간이 안 되면 날개 IV 플랫 외삽, 그 만기 스마일이 통째로 없으면
    직전 IV 를 유지하고 선물가는 선물 시세로 평가한다. 시세가 없다고 전날 값으로 소급 청산하지 않는다.
  * 레그 잔존일이 MIN_EXIT_DTE(5일) 미만이 되는 날은 그날 종가에 청산한다.
  * 선물가조차 없는 날(드묾)만 전날 청산가로 마감한다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List

from .config import MIN_EXIT_DTE, RISK_FREE, Params
from .data import interpolate_flat, interpolate_strike
from .pricing import bs76


@dataclass
class BacktestResult:
    daily: Dict[str, float] = field(default_factory=dict)      # date -> 수익률 증분
    trades: List[float] = field(default_factory=list)          # 거래별 수익률
    detail: List[tuple] = field(default_factory=list)          # (진입일, 청산일, 태그, 수익률, 보유일, 청산사유, 대체평가일수)


def _gap(d0: str, d1: str) -> int:
    return (datetime.strptime(d1, "%Y%m%d") - datetime.strptime(d0, "%Y%m%d")).days


def price_legs(legs, day, smiles_by_day, fwd_by_day, mode: str, cost_iv_pt: float, memo: dict):
    """mode: 'mid' | 'entry' | 'exit'.
    반환 (가치, 만기별 델타, 만기별 선물가, 최소 잔존일, 대체평가 여부) 또는 None (선물가조차 없을 때)."""
    smiles, fwds_today = smiles_by_day.get(day, {}), (fwd_by_day or {}).get(day, {})
    value, deltas, fwds, dte_min, fb = 0.0, defaultdict(float), {}, 10 ** 9, False
    for k, leg in enumerate(legs):
        sm = smiles.get(leg["expiry"])
        F = sm.forward if sm else fwds_today.get(leg["expiry"])
        if F is None:
            return None
        dte = leg["dte0"] - _gap(leg["d0"], day)
        iv = interpolate_strike(sm.points, leg["K"] / F) if sm else None
        if iv is None:
            fb = True
            iv = interpolate_flat(sm.points, leg["K"] / F) if sm else memo.get(k)
            if iv is None:
                return None
        memo[k] = iv
        if mode == "entry":
            iv += cost_iv_pt * (1 if leg["qty"] > 0 else -1)      # 매수는 비싸게
        elif mode == "exit":
            iv -= cost_iv_pt * (1 if leg["qty"] > 0 else -1)      # 매수 청산은 싸게
        price, delta, _ = bs76(F, leg["K"], max(dte, 0) / 365, max(iv, 1.0) / 100, RISK_FREE, leg["right"])
        value += leg["qty"] * price
        deltas[leg["expiry"]] += leg["qty"] * delta
        fwds[leg["expiry"]] = F
        dte_min = min(dte_min, dte)
    return value, deltas, fwds, dte_min, fb


def _unwind(hedge, fut_cost):
    return fut_cost * sum(abs(h) for h in hedge.values())


def run_engine(dates, rows_by_date, z, smiles_by_day, builder: Callable, p: Params,
               fwd_by_day=None) -> BacktestResult:
    daily, trades, detail = defaultdict(float), [], []
    n, i = len(dates), 0
    while i < n:
        if z[i] is None or abs(z[i]) < p.z_entry:
            i += 1
            continue
        sig_i, i = i, i + p.entry_lag                    # 신호는 sig_i 종가에서 확인, 체결은 lag일 뒤
        if i >= n:
            break
        day0 = dates[i]
        built = builder(z[sig_i], rows_by_date[day0], smiles_by_day[day0])
        if built is None:
            i = sig_i + 1
            continue
        legs, base, tag = built
        for leg in legs:
            leg.update(d0=day0, dte0=smiles_by_day[day0][leg["expiry"]].days)
        memo = {}
        ent = price_legs(legs, day0, smiles_by_day, fwd_by_day, "entry", p.cost_iv_pt, memo)
        if ent is None:
            i = sig_i + 1
            continue
        v_entry, d0, prev_f, _, _ = ent
        hedge = {e: -d for e, d in d0.items()}
        cum_hedge = -_unwind(hedge, p.fut_cost)          # 진입 헤지 비용
        prev_total, prev_exit_adj = 0.0, 0.0
        last_day, j, reason, nfb = day0, i, None, 0
        while j + 1 < n and (j - i) < p.max_hold:
            j += 1
            dj = dates[j]
            mid = price_legs(legs, dj, smiles_by_day, fwd_by_day, "mid", p.cost_iv_pt, memo)
            if mid is None:                              # 선물가조차 없음(드묾) -> 마지막 정상일 청산가로 마감
                daily[last_day] += prev_exit_adj / base
                prev_total += prev_exit_adj
                reason, j = "no_quote", j - 1
                break
            v_mid, deltas, fs, dte, fb = mid
            nfb += fb
            cum_hedge += sum(hedge[e] * (fs[e] - prev_f[e]) for e in hedge)
            zj = z[j]
            stopped = (p.stop_dz is not None and zj is not None and z[sig_i] is not None
                       and (zj if z[sig_i] > 0 else -zj) >= abs(z[sig_i]) + p.stop_dz)
            why = ("expiry" if dte < MIN_EXIT_DTE else "signal" if (zj is not None and abs(zj) < p.z_exit)
                   else "max_hold" if (j - i) >= p.max_hold else "stop" if stopped else None)
            if why:
                v_ex = price_legs(legs, dj, smiles_by_day, fwd_by_day, "exit", p.cost_iv_pt, memo)[0]
                total = v_ex - v_entry + cum_hedge - _unwind(hedge, p.fut_cost)
                daily[dj] += (total - prev_total) / base
                prev_total, reason, last_day = total, why, dj
                break
            if p.rehedge:                                # 오늘 종가에 재헤지 (거래한 선물 수량만큼 비용)
                new = {e: -d for e, d in deltas.items()}
                cum_hedge -= p.fut_cost * sum(abs(new.get(e, 0.0) - hedge.get(e, 0.0)) for e in set(new) | set(hedge))
                hedge = new
            total_mid = v_mid - v_entry + cum_hedge
            daily[dj] += (total_mid - prev_total) / base
            prev_total = total_mid
            v_ex = price_legs(legs, dj, smiles_by_day, fwd_by_day, "exit", p.cost_iv_pt, memo)[0]
            prev_exit_adj = v_ex - v_mid - _unwind(hedge, p.fut_cost)
            last_day, prev_f = dj, fs
        if reason is None:                               # 데이터 종료
            daily[last_day] += prev_exit_adj / base
            prev_total += prev_exit_adj
            reason = "data_end"
        trades.append(prev_total / base)
        detail.append((day0, last_day, tag, prev_total / base, j - i, reason, nfb))
        i = max(j, i) + 1
    return BacktestResult(dict(daily), trades, detail)


def to_equity(dates, daily: Dict[str, float]) -> List[float]:
    """누적 손익 곡선 (길이 len(dates)+1, 첫 값 0)."""
    eq = [0.0]
    for d in dates:
        eq.append(eq[-1] + daily.get(d, 0.0))
    return eq
