"""계속 매수 롤 엔진.

규칙: 항상 매수 포지션을 들고 있다가 잔존 MIN_EXIT_DTE 미만이 된 날 종가에 팔고,
다음 날 잔존 MIN_ENTRY_DTE 이상인 가장 가까운 만기로 다시 산다. 신호·손절·보유일 제한 없음.

손익 = (옵션 평가액 − 진입가) + 누적 헤지손익. 옵션 비용은 진입·청산 때 레그별로 IV를 불리하게 cost 만큼 조정.
hedge = "none"(델타헤지 없음) | "daily"(매일 종가에 선물로 델타 재헤지, 전날 헤지비율이 오늘 움직임을 받음).
선물 비용은 진입 헤지·매일 재헤지·청산 때 헤지 해제에서 거래한 선물 수량 × fut_cost (지수 포인트).

보유 중 행사가가 그날 스마일 밖으로 나가 보간이 안 되면 날개 IV 플랫 외삽, 그 만기 스마일이 통째로 없으면
직전 IV 유지로 그날을 평가한다. 시세가 없다고 그날 손익을 건너뛰거나 전날로 청산하지 않는다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from . import config as C
from .pricing import bs76, interp, interp_flat
from .structures import build


@dataclass
class Trade:
    pnl: float          # 진입 선물가 대비 비율
    reason: str         # expiry | no_fwd | data_end
    entry: str
    exit: str
    held: int           # 보유 거래일
    fallback: int       # 보간이 안 돼 외삽·직전 IV로 평가한 날 수


def _gap(d0, d1):
    return (datetime.strptime(d1, "%Y%m%d") - datetime.strptime(d0, "%Y%m%d")).days


def _unwind_cost(hedge_pos, fut_cost):
    """헤지 선물 전량을 정리할 때의 비용 (지수 포인트)."""
    return fut_cost * sum(abs(h) for h in hedge_pos.values())


def price_legs(legs, day, ds, mode, memo, cost):
    """mode: entry | mid | exit. 반환 (가치, 만기별 델타, 만기별 선물가, 최소 잔존일, 대체평가 여부) 또는 None."""
    smiles, fwd = ds.smiles.get(day, {}), ds.fwd.get(day, {})
    value, deltas, fwds, dte_min, fb = 0.0, defaultdict(float), {}, 10 ** 9, False
    for k, leg in enumerate(legs):
        sm = smiles.get(leg["expiry"])
        F = sm.forward if sm else fwd.get(leg["expiry"])
        if F is None:
            return None
        dte = leg["dte0"] - _gap(leg["d0"], day)
        iv = interp(sm.points, leg["K"] / F) if sm else None
        if iv is None:
            fb = True
            iv = interp_flat(sm.points, leg["K"] / F) if sm else memo.get(k)
            if iv is None:
                return None
        memo[k] = iv
        if mode == "entry":
            iv += cost * (1 if leg["qty"] > 0 else -1)
        elif mode == "exit":
            iv -= cost * (1 if leg["qty"] > 0 else -1)
        p, d, _ = bs76(F, leg["K"], max(dte, 0) / 365, max(iv, 1.0) / 100, leg["right"])
        value += leg["qty"] * p
        deltas[leg["expiry"]] += leg["qty"] * d
        fwds[leg["expiry"]] = F
        dte_min = min(dte_min, dte)
    return value, deltas, fwds, dte_min, fb


def run(dates, ds, structure, hedge="none", cost=C.COST_IV_PT, fut_cost=C.FUT_COST_PT):
    """반환: ({날짜: 손익 비율}, [Trade])"""
    daily, trades = defaultdict(float), []
    n, i = len(dates), 0
    while i < n:
        built = build(structure, ds.smiles.get(dates[i], {}))
        if built is None:                          # 살 수 있는 만기가 없는 날은 하루 쉰다
            i += 1
            continue
        legs, base, dte0 = built
        for leg in legs:
            leg.update(d0=dates[i], dte0=dte0)
        memo = {}
        v0, d0, prevF, _, _ = price_legs(legs, dates[i], ds, "entry", memo, cost)
        hedge_pos = {e: -d for e, d in d0.items()} if hedge == "daily" else {}
        cum_h, prev_tot, prev_adj = -_unwind_cost(hedge_pos, fut_cost), 0.0, 0.0   # 진입 헤지 비용
        last_day, j, why, nfb = dates[i], i, None, 0
        while j + 1 < n:
            j += 1
            dj = dates[j]
            mid = price_legs(legs, dj, ds, "mid", memo, cost)
            if mid is None:                        # 선물가조차 없는 날(드묾): 전날 청산가로 마감
                daily[last_day] += prev_adj / base
                prev_tot += prev_adj
                why, j = "no_fwd", j - 1
                break
            vm, dlt, Fs, dte, fb = mid
            nfb += fb
            cum_h += sum(h * (Fs[e] - prevF[e]) for e, h in hedge_pos.items())
            if dte < C.MIN_EXIT_DTE:               # 롤: 오늘 종가에 판다
                v_ex = price_legs(legs, dj, ds, "exit", memo, cost)[0]
                tot = v_ex - v0 + cum_h - _unwind_cost(hedge_pos, fut_cost)   # 청산 때 헤지 해제
                daily[dj] += (tot - prev_tot) / base
                prev_tot, why, last_day = tot, "expiry", dj
                break
            if hedge == "daily":                   # 오늘 종가에 재헤지 (거래한 선물 수량만큼 비용)
                new = {e: -d for e, d in dlt.items()}
                cum_h -= fut_cost * sum(abs(new.get(e, 0.0) - hedge_pos.get(e, 0.0))
                                        for e in set(new) | set(hedge_pos))
                hedge_pos = new
            tot = vm - v0 + cum_h
            daily[dj] += (tot - prev_tot) / base
            prev_tot = tot
            prev_adj = (price_legs(legs, dj, ds, "exit", memo, cost)[0] - vm
                        - _unwind_cost(hedge_pos, fut_cost))
            last_day, prevF = dj, Fs
        if why is None:                            # 표본 끝: 마지막 날 청산가
            daily[last_day] += prev_adj / base
            prev_tot += prev_adj
            why = "data_end"
        trades.append(Trade(prev_tot / base, why, dates[i], last_day,
                            max(1, dates.index(last_day) - i), nfb))
        i = max(j, i) + 1
    return dict(daily), trades
