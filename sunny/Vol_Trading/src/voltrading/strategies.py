"""포지션 빌더: (z값, 당일 행 정보, 스마일 dict) → (레그 목록, 기준가, 태그) 또는 None.

전략 1 — VRP (Short Volatility)
  z > 0  (VRP 높음, IV > HV) → ATM 스트래들 매도
  z < 0  (VRP 낮음, IV ≈ HV) → ATM 스트래들 매수  ← Long Volatility

전략 2 — Long Volatility (순수 Vega 롱)
  VRP z < -threshold  (IV가 RV 대비 저렴) → ATM 스트래들 매수
  → 발표 슬라이드 11의 'Long vol' 전략
"""
from __future__ import annotations

from . import config as C
from .data import interpolate
from .pricing import TARGET_VEGA_UNIT, bs76


def _dte_mult(dte: int) -> float:
    """잔존일에 따른 사이즈 배수 (10일 미만 0, 10~20일 선형 0.2→1.0, 20일 이상 1.0)."""
    if dte >= C.DTE_TAPER_FULL:
        return 1.0
    if dte < C.MIN_ENTRY_DTE:
        return 0.0
    span = C.DTE_TAPER_FULL - C.MIN_ENTRY_DTE
    frac = (dte - C.MIN_ENTRY_DTE) / span
    return C.DTE_TAPER_FLOOR + (1.0 - C.DTE_TAPER_FLOOR) * max(0.0, min(1.0, frac))


def vrp_builder(zi, row, smiles):
    """VRP 전략 빌더.

    z > 0 → IV 고평가 → ATM 스트래들 매도 (Short Volatility, VRP 수취)
    z < 0 → IV 저평가 → ATM 스트래들 매수 (Long Volatility, 위기 헤지)

    베가 정규화: TARGET_VEGA_UNIT 기준으로 수량 조정.
    """
    expiry = row["near_expiry"]
    sm = smiles.get(expiry)
    if sm is None or sm.days < C.MIN_ENTRY_DTE:
        return None
    mult = _dte_mult(sm.days)
    if mult == 0:
        return None
    F0, T0 = sm.forward, sm.days / 365
    iv0 = interpolate(sm.points, 1.0)
    if iv0 is None:
        return None
    vega = bs76(F0, F0, T0, iv0 / 100, C.RISK_FREE, "C")[2]
    if vega <= 0:
        return None
    sign = -1 if zi > 0 else 1          # z>0: 매도(sign=-1), z<0: 매수(sign=+1)
    qty  = sign * (TARGET_VEGA_UNIT / (2 * vega)) * mult
    legs = [
        dict(expiry=expiry, right="C", K=F0, qty=qty),
        dict(expiry=expiry, right="P", K=F0, qty=qty),
    ]
    tag = "SHORT_STRADDLE" if sign < 0 else "LONG_STRADDLE"
    return legs, F0, tag


def longvol_builder(zi, row, smiles):
    """Long Volatility 전용 빌더.

    z < -threshold → IV 저렴 → ATM 스트래들 매수만 허용.
    (VRP 전략의 롱 방향만 분리한 버전 — 헤지·위기대응 관점)
    """
    if zi >= 0:          # 음수(IV 저렴)일 때만 진입
        return None
    expiry = row["near_expiry"]
    sm = smiles.get(expiry)
    if sm is None or sm.days < C.MIN_ENTRY_DTE:
        return None
    mult = _dte_mult(sm.days)
    if mult == 0:
        return None
    F0, T0 = sm.forward, sm.days / 365
    iv0 = interpolate(sm.points, 1.0)
    if iv0 is None:
        return None
    vega = bs76(F0, F0, T0, iv0 / 100, C.RISK_FREE, "C")[2]
    if vega <= 0:
        return None
    qty  = (TARGET_VEGA_UNIT / (2 * vega)) * mult
    legs = [
        dict(expiry=expiry, right="C", K=F0, qty=qty),
        dict(expiry=expiry, right="P", K=F0, qty=qty),
    ]
    return legs, F0, "LONG_STRADDLE_ONLY"


def shortvol_builder(zi, row, smiles):
    """Short Volatility 전용 빌더.

    z > +threshold → IV 비쌈 → ATM 스트래들 매도만 허용.
    (순수 VRP 수취 전략 — 발표 슬라이드 10)
    """
    if zi <= 0:          # 양수(IV 비쌈)일 때만 진입
        return None
    expiry = row["near_expiry"]
    sm = smiles.get(expiry)
    if sm is None or sm.days < C.MIN_ENTRY_DTE:
        return None
    mult = _dte_mult(sm.days)
    if mult == 0:
        return None
    F0, T0 = sm.forward, sm.days / 365
    iv0 = interpolate(sm.points, 1.0)
    if iv0 is None:
        return None
    vega = bs76(F0, F0, T0, iv0 / 100, C.RISK_FREE, "C")[2]
    if vega <= 0:
        return None
    qty  = -(TARGET_VEGA_UNIT / (2 * vega)) * mult   # 매도 → 음수 수량
    legs = [
        dict(expiry=expiry, right="C", K=F0, qty=qty),
        dict(expiry=expiry, right="P", K=F0, qty=qty),
    ]
    return legs, F0, "SHORT_STRADDLE_ONLY"
