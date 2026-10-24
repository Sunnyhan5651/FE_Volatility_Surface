"""Black-76 가격·델타·베가 (선물 기초)."""
from __future__ import annotations

import math

from .config import REF_F, REF_SIGMA, REF_T, RISK_FREE


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs76(F: float, K: float, T: float, sigma: float, r: float, right: str):
    """(가격, 델타, 베가) 반환. sigma는 소수(0.30=30%), 베가는 IV 1포인트당 값."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(0.0, (F - K) if right == "C" else (K - F))
        delta = 1.0 if (right == "C" and F > K) else (-1.0 if right == "P" and F < K else 0.0)
        return intrinsic, delta, 0.0
    sqrt_t = math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    disc = math.exp(-r * T)
    vega = F * disc * norm_pdf(d1) * sqrt_t / 100.0
    if right == "C":
        return disc * (F * norm_cdf(d1) - K * norm_cdf(d2)), disc * norm_cdf(d1), vega
    return disc * (K * norm_cdf(-d2) - F * norm_cdf(-d1)), disc * (norm_cdf(d1) - 1), vega


# VRP 스트래들 수량을 베가 기준으로 정규화하는 기준 단위 (참조 시나리오의 스트래들 베가)
TARGET_VEGA_UNIT = 2 * bs76(REF_F, REF_F, REF_T, REF_SIGMA, RISK_FREE, "C")[2]
