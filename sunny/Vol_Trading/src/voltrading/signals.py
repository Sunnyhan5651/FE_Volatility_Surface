"""일별 지표(VRP, IV-HV 스프레드) 계산 및 z-score 신호 생성."""
from __future__ import annotations

import math
import statistics as st
from typing import Dict, List

from .data import Dataset, interpolate


def compute_indicators(ds: Dataset) -> List[dict]:
    """일별 지표 행 목록.
    반환 dict 키:
      date, near_expiry, far_expiry, near_dte, far_dte
      atm_iv     : 근월물 ATM IV (%)
      rv20       : 20일 실현변동성 (%)
      vrp        : atm_iv - rv20  (양수 = IV > HV → short vol 신호)
      term_slope : 원월 ATM IV - 근월 ATM IV (양수 = 기간구조 우상향)
    """
    rows = []
    for day in sorted(ds.smiles_by_day):
        order = sorted(ds.smiles_by_day[day].values(), key=lambda s: s.days)
        if len(order) < 2:
            continue
        near, far = order[0], order[-1]
        near_atm = interpolate(near.points, 1.0)
        far_atm  = interpolate(far.points,  1.0)
        rv = ds.rv.get(day)
        rows.append(dict(
            date=day,
            near_expiry=near.expiry,
            far_expiry=far.expiry,
            near_dte=near.days,
            far_dte=far.days,
            atm_iv=near_atm,
            rv20=rv,
            vrp=(near_atm - rv)  if (near_atm is not None and rv is not None) else None,
            term_slope=(far_atm - near_atm) if (near_atm is not None and far_atm is not None) else None,
        ))
    return rows


def rolling_z(rows: List[dict], key: str, window: int = 40) -> list:
    """직전 window개 유효값 기준 z-score."""
    vals = [r[key] for r in rows]
    z = [None] * len(vals)
    for i in range(len(vals)):
        if vals[i] is None:
            continue
        hist = [v for v in vals[max(0, i - window): i] if v is not None]
        if len(hist) < max(10, window // 2):
            continue
        mu = sum(hist) / len(hist)
        sd = math.sqrt(sum((v - mu) ** 2 for v in hist) / len(hist))
        if sd == 0:
            continue
        z[i] = (vals[i] - mu) / sd
    return z


def robust_z(rows: List[dict], key: str, window: int = 40) -> list:
    """중앙값·MAD(×1.4826) 기반 robust z-score."""
    vals = [r[key] for r in rows]
    z = [None] * len(vals)
    for i in range(len(vals)):
        if vals[i] is None:
            continue
        hist = [v for v in vals[max(0, i - window): i] if v is not None]
        if len(hist) < max(10, window // 2):
            continue
        med = st.median(hist)
        mad = 1.4826 * st.median([abs(v - med) for v in hist])
        if mad == 0:
            continue
        z[i] = (vals[i] - med) / mad
    return z
