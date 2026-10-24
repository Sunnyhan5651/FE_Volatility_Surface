"""포지션 빌더: 신호 z와 당일 스마일로 (레그 목록, 수익률 기준가, 태그)를 만든다."""
from __future__ import annotations

from . import config as C
from .data import interpolate_strike
from .indicators import skew25
from .pricing import TARGET_VEGA_UNIT, bs76


def dte_size_multiplier(dte: int) -> float:
    """잔존일 10일 미만 0(진입 금지는 빌더에서), 10~20일 0.2→1.0 선형, 20일 이상 1.0."""
    if dte >= C.DTE_TAPER_FULL:
        return 1.0
    span = C.DTE_TAPER_FULL - C.MIN_ENTRY_DTE
    frac = (dte - C.MIN_ENTRY_DTE) / span if span > 0 else 1.0
    return C.DTE_TAPER_FLOOR + (1.0 - C.DTE_TAPER_FLOOR) * max(0.0, min(1.0, frac))


def vrp_builder(zi, row, smiles):
    """z>0 (IV가 RV 대비 비쌈) -> ATM 스트래들 매도, z<0 -> 매수. 베가 정규화 + 잔존일 사이징."""
    expiry = row["near_expiry"]
    sm = smiles.get(expiry)
    if sm is None or sm.days < C.MIN_ENTRY_DTE:
        return None
    F0, T0 = sm.forward, sm.days / 365
    iv0 = interpolate_strike(sm.points, 1.0)
    if iv0 is None:
        return None
    sign = -1 if zi > 0 else 1
    vega = bs76(F0, F0, T0, iv0 / 100, C.RISK_FREE, "C")[2]
    if vega <= 0:
        return None
    qty = sign * (TARGET_VEGA_UNIT / (2 * vega)) * dte_size_multiplier(sm.days)
    legs = [dict(expiry=expiry, right="C", K=F0, qty=qty), dict(expiry=expiry, right="P", K=F0, qty=qty)]
    return legs, F0, ("SELL" if sign < 0 else "BUY")


def make_skew_builder(legs_mode: str = "moneyness", min_dte: int | None = None):
    """리스크리버설 빌더.
    legs_mode : 'moneyness' (풋 0.90F / 콜 1.10F) 또는 'delta25' (25-delta 풋/콜 행사가)
    min_dte   : 잔존일이 이보다 짧으면 진입 금지 (None = 필터 없음)
    z>0 (풋 스큐 비쌈) -> RR 매도 (풋 매도 + 콜 매수), z<0 -> RR 매수.
    """
    def builder(zi, row, smiles):
        sm = smiles.get(row["near_expiry"])
        if sm is None or (min_dte is not None and sm.days < min_dte):
            return None
        F0 = sm.forward
        if legs_mode == "delta25":
            s = skew25(sm)
            if s is None:
                return None
            kp, kc = s[1] * F0, s[2] * F0
        else:
            if interpolate_strike(sm.points, 0.90) is None or interpolate_strike(sm.points, 1.10) is None:
                return None
            kp, kc = 0.90 * F0, 1.10 * F0
        sign = -1 if zi > 0 else 1
        legs = [dict(expiry=sm.expiry, right="P", K=kp, qty=sign), dict(expiry=sm.expiry, right="C", K=kc, qty=-sign)]
        tag = ("SELL_RR" if sign < 0 else "BUY_RR") + ("25" if legs_mode == "delta25" else "")
        return legs, F0, tag
    return builder


def calendar_builder(zi, row, smiles):
    """근월·원월 ATM 스트래들을 베가 중립으로. z>0 (원월 비쌈) -> 근월 매수 / 원월 매도."""
    ne, fe = row["near_expiry"], row["far_expiry"]
    sn, sf = smiles.get(ne), smiles.get(fe)
    if sn is None or sf is None:
        return None
    ivn, ivf = interpolate_strike(sn.points, 1.0), interpolate_strike(sf.points, 1.0)
    if ivn is None or ivf is None:
        return None
    vn = bs76(sn.forward, sn.forward, sn.days / 365, ivn / 100, C.RISK_FREE, "C")[2]
    vf = bs76(sf.forward, sf.forward, sf.days / 365, ivf / 100, C.RISK_FREE, "C")[2]
    if vn <= 0 or vf <= 0:
        return None
    s_near = 1 if zi > 0 else -1
    qn, qf = s_near * TARGET_VEGA_UNIT / (2 * vn), -s_near * TARGET_VEGA_UNIT / (2 * vf)
    legs = [dict(expiry=ne, right="C", K=sn.forward, qty=qn), dict(expiry=ne, right="P", K=sn.forward, qty=qn),
            dict(expiry=fe, right="C", K=sf.forward, qty=qf), dict(expiry=fe, right="P", K=sf.forward, qty=qf)]
    return legs, (sn.forward + sf.forward) / 2, ("LONG_NEAR" if s_near > 0 else "SHORT_NEAR")
