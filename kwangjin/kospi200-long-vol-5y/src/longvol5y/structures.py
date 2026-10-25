"""옵션 구조 정의와 레그 생성 (모두 변동성 매수 방향).

  스트래들 매수          풋 K=F + 콜 K=F
  스트랭글 매수          풋 날개 + 콜 날개
  스트랩 매수            풋 1 + 콜 2 (K=F)   상승 쪽 비중이 큼 (= 스트래들 + 선물 매수 1/3)
  스트립 매수            풋 2 + 콜 1 (K=F)   하락 쪽 비중이 큼 (= 스트래들 + 선물 매도 1/3)
  콜 버터플라이 매도     콜 K1 매도 + 콜 K2=F 2개 매수 + 콜 K3 매도
                         (= 날개에서 이익이 막힌 스트래들 매수, 롱 버터플라이의 정반대)

날개: "kf" = K/F 0.90 / 1.10, "d25" = 그날 스마일 IV 기준 25델타 풋 / 콜 행사가.
크기
  버터플라이 외: 구조 전체 베가 = 진입일 ATM 스트래들 1개의 베가 (구조끼리 같은 변동성 노출로 비교)
  버터플라이:   몸통 = ATM 콜 2개(≈ 스트래들 1개 베가). 날개는 꼬리 손익이 양쪽 모두 0이 되도록
                w1 = 2(K3−K2)/(K3−K1), w3 = 2(K2−K1)/(K3−K1)  (행사가 간격이 같으면 1 : 2 : 1)
                베가를 맞추면 몸통과 날개가 상쇄돼 수량이 폭주하므로 맞추지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config as C
from .pricing import bs76, interp, strike_for_delta

QTY = {"straddle": (1, 1), "strangle": (1, 1), "strap": (1, 2), "strip": (2, 1)}   # (풋, 콜)


@dataclass(frozen=True)
class Structure:
    kind: str           # straddle | strangle | strap | strip | butterfly
    wing: str | None    # None | "kf" | "d25"

    @property
    def name(self) -> str:
        base = {"straddle": "스트래들", "strangle": "스트랭글", "strap": "스트랩", "strip": "스트립",
                "butterfly": "콜 버터플라이 매도"}[self.kind]
        if self.wing == "kf":
            return f"{base} {C.WING_KF[0]:.2f}/{C.WING_KF[1]:.2f}"
        if self.wing == "d25":
            return f"{base} {round(C.WING_DELTA * 100)}Δ"
        return base


def wing_strikes(smile, wing):
    """(풋 쪽 K/F, 콜 쪽 K/F) 또는 None."""
    if wing == "kf":
        return C.WING_KF
    if wing == "d25":
        mp, mc = strike_for_delta(smile, "P"), strike_for_delta(smile, "C")
        return None if mp is None or mc is None else (mp, mc)
    return (1.0, 1.0)


def _legs(st: Structure, sm):
    strikes = wing_strikes(sm, st.wing)
    if strikes is None:
        return None
    mp, mc = strikes
    ivp, ivc, iva = interp(sm.points, mp), interp(sm.points, mc), interp(sm.points, 1.0)
    if ivp is None or ivc is None or iva is None:
        return None
    F, T, e = sm.forward, sm.days / 365, sm.expiry

    if st.kind == "butterfly":                     # 날개 매도, 몸통(ATM 콜 2개) 매수
        k1, k2, k3 = mp * F, F, mc * F
        w1, w3 = 2 * (k3 - k2) / (k3 - k1), 2 * (k2 - k1) / (k3 - k1)
        return [dict(expiry=e, right="C", K=k1, qty=-w1, m=mp),
                dict(expiry=e, right="C", K=k3, qty=-w3, m=mc),
                dict(expiry=e, right="C", K=k2, qty=2.0, m=1.0)]

    qp, qc = QTY[st.kind]
    v_atm = bs76(F, F, T, iva / 100, "C")[2]
    vega = qp * bs76(F, mp * F, T, ivp / 100, "P")[2] + qc * bs76(F, mc * F, T, ivc / 100, "C")[2]
    if vega <= 0:
        return None
    scale = 2 * v_atm / vega
    return [dict(expiry=e, right="P", K=mp * F, qty=qp * scale, m=mp),
            dict(expiry=e, right="C", K=mc * F, qty=qc * scale, m=mc)]


def build(st: Structure, smiles_today: dict):
    """잔존 MIN_ENTRY_DTE 이상인 가장 가까운 만기로 레그 생성. 반환: (legs, 기준 선물가, 잔존일) 또는 None."""
    for sm in sorted(smiles_today.values(), key=lambda s: s.days):
        if sm.days < C.MIN_ENTRY_DTE:
            continue
        legs = _legs(st, sm)
        if legs is not None:
            return legs, sm.forward, sm.days
    return None
