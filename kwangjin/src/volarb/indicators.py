"""지표(스큐·기간구조·VRP)와 신호 변형(25-delta, 3일 평활), z-score."""
from __future__ import annotations

import math
import statistics as st
from typing import Dict, List

from .config import MAX_STRIKE_GAP
from .data import Dataset, interpolate_strike

# N(d1)=0.75 -> 25-delta 풋, N(d1)=0.25 -> 25-delta 콜 (비할인 선물델타 기준)
TARGET_D1 = 0.6744897501960817


def compute_indicators(ds: Dataset) -> List[dict]:
    """일별 행 목록. 각 지표는 서로 독립적으로 None 가능 (한 지표가 없어도 다른 지표는 보존)."""
    rows = []
    for day in sorted(ds.smiles_by_day):
        order = sorted(ds.smiles_by_day[day].values(), key=lambda s: s.days)
        if len(order) < 2:
            continue
        near, far = order[0], order[-1]
        near_atm = interpolate_strike(near.points, 1.0)
        far_atm = interpolate_strike(far.points, 1.0)
        low, high = interpolate_strike(near.points, 0.90), interpolate_strike(near.points, 1.10)
        rv = ds.rv20.get(day)
        rows.append(dict(
            date=day, near_expiry=near.expiry, far_expiry=far.expiry,
            near_dte=near.days, far_dte=far.days, near_atm=near_atm,
            skew=(low - high) if (low is not None and high is not None) else None,
            term_slope=(far_atm - near_atm) if (near_atm is not None and far_atm is not None) else None,
            vrp=(near_atm - rv) if (near_atm is not None and rv is not None) else None,
            rv20=rv))
    return rows


# --------------------------------------------------------------------- 25-delta
def _d1_at(sm, x):
    iv = interpolate_strike(sm.points, x)
    if iv is None:
        return None, None
    s, T = iv / 100, sm.days / 365
    return (math.log(1 / x) + 0.5 * s * s * T) / (s * math.sqrt(T)), iv


def delta_strike(sm, side: str):
    """25-delta 풋('P')/콜('C')의 (K/F, IV). 행사가를 훑어 d1=±TARGET_D1 지점을 선형 근사."""
    tgt = TARGET_D1 if side == "P" else -TARGET_D1
    prev = None
    for k in range(161):
        x = round(0.80 + 0.0025 * k, 5)
        d, _ = _d1_at(sm, x)
        if d is None:
            prev = None
            continue
        if prev is not None and (prev[1] - tgt) * (d - tgt) <= 0 and prev[1] != d:
            xr = prev[0] + (tgt - prev[1]) / (d - prev[1]) * (x - prev[0])
            d2, iv2 = _d1_at(sm, xr)
            if d2 is not None:
                return xr, iv2
        prev = (x, d)
    return None


def skew25(sm):
    """(IV25풋 − IV25콜, 풋 K/F, 콜 K/F) 또는 None."""
    p, c = delta_strike(sm, "P"), delta_strike(sm, "C")
    if p is None or c is None:
        return None
    return p[1] - c[1], p[0], c[0]


def add_signals(rows: List[dict], ds: Dataset) -> List[dict]:
    """25-delta 스큐와 3일 평활 신호를 행에 추가."""
    for r in rows:
        sm = ds.smiles_by_day[r["date"]].get(r["near_expiry"])
        s = skew25(sm) if sm else None
        r["skew25"] = s[0] if s else None
        r["skew25_put_m"], r["skew25_call_m"] = (s[1], s[2]) if s else (None, None)
    for src, dst in (("skew", "skew_sma3"), ("skew25", "skew25_sma3")):
        for r, v in zip(rows, sma_within_expiry(rows, src, n=3, min_valid=2)):
            r[dst] = v
    return rows


def sma_within_expiry(rows, key, n=3, min_valid=2):
    """같은 근월물 안에서만 최근 n개 평균 (유효값 min_valid개 이상, 당일 값 필수). 롤오버 경계는 넘지 않음."""
    out = []
    for i, r in enumerate(rows):
        win = [rows[j][key] for j in range(max(0, i - n + 1), i + 1)
               if rows[j]["near_expiry"] == r["near_expiry"] and rows[j][key] is not None]
        out.append(sum(win) / len(win) if len(win) >= min_valid and r[key] is not None else None)
    return out


# --------------------------------------------------------------------- z-score
def rolling_z(rows, key, window=40) -> list:
    """직전 window개 행(데이터 있는 날만 계산에 사용)의 평균·표준편차 기준 z-score."""
    vals = [r[key] for r in rows]
    z = [None] * len(vals)
    for i in range(len(vals)):
        if vals[i] is None:
            continue
        hist = [v for v in vals[max(0, i - window):i] if v is not None]
        if len(hist) < max(10, window // 2):
            continue
        mu, sd = st.mean(hist), st.pstdev(hist)
        if sd == 0:
            continue
        z[i] = (vals[i] - mu) / sd
    return z


def robust_z(rows, key, window=40) -> list:
    """평균·표준편차 대신 중앙값·MAD(×1.4826) 사용."""
    vals = [r[key] for r in rows]
    z = [None] * len(vals)
    for i in range(len(vals)):
        if vals[i] is None:
            continue
        hist = [v for v in vals[max(0, i - window):i] if v is not None]
        if len(hist) < max(10, window // 2):
            continue
        med = st.median(hist)
        mad = 1.4826 * st.median([abs(v - med) for v in hist])
        if mad == 0:
            continue
        z[i] = (vals[i] - med) / mad
    return z
